"""Service layer: everything the UI needs, as plain functions over DuckDB.
Streamlit calls these directly today; FastAPI will wrap the same functions later. No UI code here."""
from __future__ import annotations
import json, datetime as dt, uuid
from pathlib import Path
import duckdb, pandas as pd, yaml

import os, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
DB = paths.DB  # ROYAL_DB: point tests at a copy while the app holds the lock
CATALOG = paths.RULES_CATALOG
_CAT = yaml.safe_load(open(CATALOG))
RULES = _CAT["rules"]
TIER_LABEL = {"violation": "위반 가능", "advisory": "참고"}
REASON_CODES = [("preapproved", "사전 승인·품의 있음"), ("trip_extended", "출장 일정 변경·연장"), ("business_confirmed", "업무 관련성 확인됨"),
                ("data_error", "데이터 오류(주소·시간·계정)"), ("legit_mismatch", "정당한 불일치(환율·매입일·부분취소)"), ("duplicate_flag", "다른 플래그와 중복"),
                ("need_evidence", "증빙 요청 필요"), ("other", "기타")]

_con = None
def con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        _con = duckdb.connect(str(DB))
        if paths.MACROS: _con.execute(paths.macros_sql()).fetchall()
        _con.execute("""CREATE TABLE IF NOT EXISTS reviews(review_id VARCHAR, tx_id BIGINT, rule_id VARCHAR, decision VARCHAR, reason_code VARCHAR,
                        memo VARCHAR, reviewer VARCHAR, created_at TIMESTAMP, superseded_by VARCHAR)""").fetchall()
        _con.execute("CREATE TABLE IF NOT EXISTS ui_events(ts TIMESTAMP, reviewer VARCHAR, event VARCHAR, payload VARCHAR)").fetchall()
        _con.execute("""CREATE TABLE IF NOT EXISTS queue(queue_id VARCHAR, period_from DATE, period_to DATE, tx_id BIGINT, queue_source VARCHAR,
                        selection_prob DOUBLE, rank_in_source INTEGER, built_at TIMESTAMP, seed INTEGER, params VARCHAR)""").fetchall()
    return _con
def q(sql, params=None) -> pd.DataFrame: return con().execute(sql, params or []).df()
def mask(name): return name if not isinstance(name, str) or len(name) < 2 else name[0] + "*" * (len(name) - 2) + name[-1]
def rule_tier(rid): return RULES.get(rid, {}).get("tier", "advisory")
def rule_class(rid): return TIER_LABEL[rule_tier(rid)]
def rule_explain(rid): return RULES.get(rid, {}).get("explain", "")

# ---------- rules ----------
def list_rules() -> pd.DataFrame:
    return pd.DataFrame([dict(rule_id=k, name=v["name"], tier=v["tier"], rule_class=TIER_LABEL[v["tier"]], data_ready=v["data_ready"],
                              params=json.dumps(v["params"], ensure_ascii=False), explain=v.get("explain", ""), policy_ref=v.get("policy_ref", "")) for k, v in RULES.items()])
RULE_NAME = {r.rule_id: r.name for r in list_rules().itertuples()}

# ---------- latest review per (tx, rule) ----------
_LATEST = """latest as (select * from reviews where superseded_by is null)"""

def get_summary(date_from=None, date_to=None, scope="all") -> pd.DataFrame:
    where, p = _tx_where(date_from, date_to, scope)
    return q(f"""with {_LATEST}
      select f.rule_id, count(*) flagged, count(l.decision) reviewed,
             sum(case when l.decision='violation' then 1 else 0 end) violation, sum(case when l.decision='ok' then 1 else 0 end) ok,
             round(100.0*sum(case when l.decision='violation' then 1 else 0 end)/nullif(count(l.decision),0),1) hit_rate_pct
      from flags f join tx_active t using(tx_id) left join latest l on l.tx_id=f.tx_id and l.rule_id=f.rule_id
      where {where} group by 1 order by 1""", p).assign(name=lambda d: d.rule_id.map(RULE_NAME), rule_class=lambda d: d.rule_id.map(rule_class))

def _tx_where(date_from, date_to, scope):
    w, p = ["1=1"], []
    if date_from: w.append("t.tx_date >= ?"); p.append(date_from)
    if date_to: w.append("t.tx_date <= ?"); p.append(date_to)
    if scope == "leaders": w.append("t.rank in ('팀장','본부장','담당','부문장','법인장','TF장','CCO','CoE장')")
    return " and ".join(w), p

def list_flags(rule_ids=None, depts=None, date_from=None, date_to=None, min_total=None, review_status=None, sort="total", page=1, page_size=100, synthetic_only=None):
    where, p = _tx_where(date_from, date_to, "all")
    if rule_ids: where += f" and f.rule_id in ({','.join('?'*len(rule_ids))})"; p += list(rule_ids)
    if depts: where += f" and t.dept in ({','.join('?'*len(depts))})"; p += list(depts)
    if min_total: where += " and t.total >= ?"; p.append(min_total)
    if synthetic_only is not None: where += " and t.is_synthetic = ?"; p.append(synthetic_only)
    has_score = _has_table("tx_score")
    order = {"total": "t.total desc, t.tx_id", "rules": "n_rules desc, t.total desc, t.tx_id", "date": "t.tx_ts desc, t.tx_id",
             "score": "score desc nulls last, t.total desc, t.tx_id", "learned": "score_learned desc nulls last, t.total desc, t.tx_id"}[sort if has_score or sort in ("total","rules","date") else "rules"]  # tx_id tiebreak: deterministic
    score_sel = "max(sc.score) score, max(sc.score_learned) score_learned," if has_score else "null::double score, null::double score_learned,"
    score_join = "left join tx_score sc on sc.tx_id = t.tx_id" if has_score else ""
    status_filter = {"unreviewed": "having count(l.decision)=0", "reviewed": "having count(l.decision)>0", "violation": "having bool_or(l.decision='violation')", None: ""}[review_status]
    df = q(f"""with {_LATEST}
      select t.tx_id, t.tx_ts, t.emp_id, t.emp_name, t.dept, t.rank, t.account_policy, t.merchant, t.mcc_name, t.total, t.is_synthetic,
             list(distinct f.rule_id order by f.rule_id) rules, count(distinct f.rule_id) n_rules,
             max(case f.severity when 'violation' then 2 else 1 end) sev,  -- 2 = at least one rule with written-policy basis
             coalesce(max(l.decision), 'unreviewed') review_status, {score_sel} 1 one
      from flags f join tx_active t using(tx_id) left join latest l on l.tx_id=f.tx_id and l.rule_id=f.rule_id {score_join}
      where {where} group by all {status_filter} order by {order} limit ? offset ?""", p + [page_size, (page - 1) * page_size])
    df["emp_name"] = df.emp_name.map(mask); return df

def get_transaction(tx_id) -> dict:
    r = q("select * from transactions where tx_id=?", [tx_id]).iloc[0].to_dict(); r["emp_name"] = mask(r["emp_name"]); return r

def evidence_text(rule_id, ev: dict) -> str:
    g = lambda k, d="": ev.get(k, d)
    T = {"R01": lambda: f"{g('date')}({g('weekday')}) 휴일에 {g('mcc')}에서 {g('total'):,}원 ({g('account')})",
         "R02": lambda: f"{g('leave_type')} {g('leave_hours')}시간 휴가일 {g('time')}에 {g('mcc')} {g('total'):,}원",
         "R03": lambda: f"같은 가맹점({g('merchant')})에서 {g('window_min')}분 안에 {g('count_in_window')}건, 합계 {g('group_total'):,}원 (기준 {g('near_limit'):,}원)",
         "R04": lambda: f"{g('mcc')}에서 {g('total'):,}원 단위 금액 결제. 적요: {g('memo')}",
         "R05": lambda: f"가맹점 지역({g('merchant_sigungu')})이 주거지({g('home_sigungu')})와 같고 근무지({g('work_sigungu')})와 다름. {g('time')} {g('mcc')} {g('total'):,}원",
         "R06": lambda: {"same_person": f"{g('window_min')}분 안에 {g('this_sigungu')}와 {g('other_sigungu')} 두 곳에서 결제", "named_attendee_elsewhere": f"적요에 적힌 동석자가 같은 시각 {g('other_sigungu')}에서 결제", "counterpart": "다른 거래의 동석자로 지목됐으나 같은 시각 다른 지역에서 결제"}.get(g('kind'), ""),
         "R07": lambda: f"{g('trip_type')}({g('trip')}) 중 {g('merchant_sido')} 지역에서 {g('mcc')} {g('total'):,}원 (주거지 {g('home_sido')}, 근무지 {g('work_sido')})",
         "R08": lambda: f"금지 업종 {g('mcc')}, 계정 {g('account')}, {g('weekday')}요일 {g('time')}, {g('total'):,}원",
         "R09": lambda: f"같은 날 주유 {g('same_day_count') or 1}회 / 14일 내 {g('count_in_14d') or 1}회 (기준: 하루 {g('per_day')}회, 14일 {g('per_window')}회)",
         "R10": lambda: f"증빙 필수 업종 {g('mcc')} {g('total'):,}원인데 첨부 없음 (계정 {g('account')})",
         "R11": lambda: f"업종 {g('mcc')}와 계정 {g('account')} 불일치" + (" — 해외출장 중 식사를 출장비 외 계정으로" if g('reason') == 'overseas_trip_meal_not_trip_account' else " — 금지 업종을 접대비 외 계정으로"),
         "R12": lambda: f"{g('badged_in_at')} 사옥 입문 {g('minutes_before_purchase')}분 뒤 {g('merchant_sido')}에서 결제 (근무지 {g('work_sido')}). 같은 패턴 {g('repeat_count')}회",
         "R13": lambda: f"개인물품 의심 점수 {g('score')}/4: 적요 키워드 {'O' if g('memo_keyword') else 'X'}, 쇼핑 업종 {'O' if g('shopping_mcc') else 'X'}, 심야·휴일 {'O' if g('off_hours') else 'X'}, 증빙 {'있음' if g('has_attachment') else '없음'}",
         "R14": lambda: f"{g('trip_type')}({g('trip')}) 중 {g('mcc')} {g('total'):,}원을 {g('account')}로 결제",
         "R15": lambda: f"출장({g('trip')}) 종료 {g('days_before_end')}일 전 복귀 교통편 결제, 이후 출장지 소비 없음",
         "R16": lambda: f"{g('peer_group')} 동료 중앙값 {g('peer_median'):,.0f}원의 {g('ratio')}배인 {g('total'):,}원 (비교 {g('peer_n')}건)",
         "R17": lambda: f"자택방문교통비인데 {g('merchant_sido')} 지역 {g('mcc')} (주거지 {g('home_sido')}, 근무지 {g('work_sido')})",
         "R18": lambda: f"승인자 주거지({g('approver_sigungu')})와 가맹점 지역이 같음. {g('time')} {g('mcc')} {g('total'):,}원",
         "R21": lambda: f"{g('mcc')} {g('total'):,}원, 적요 참석 {g('attendees_in_memo') or '?'}명: {g('memo')}"}
    try: return T.get(rule_id[:3], lambda: json.dumps(ev, ensure_ascii=False))()
    except Exception: return json.dumps(ev, ensure_ascii=False)

def get_evidence(tx_id) -> list[dict]:
    df = q("select rule_id, evidence, related_tx_ids, severity, rule_version from flags where tx_id=? order by severity desc, rule_id", [tx_id])
    out = []
    for r in df.itertuples():
        ev = json.loads(r.evidence) if isinstance(r.evidence, str) else r.evidence
        rel = list_flags_by_ids([int(x) for x in (r.related_tx_ids if r.related_tx_ids is not None else [])])
        out.append(dict(rule_id=r.rule_id, rule_name=RULE_NAME.get(r.rule_id, r.rule_id), rule_class=rule_class(r.rule_id), severity=r.severity,
                        evidence=ev, evidence_text=evidence_text(r.rule_id, ev), related_tx=rel, rule_version=r.rule_version))
    return out

def list_flags_by_ids(ids):
    if not ids: return pd.DataFrame()
    df = q(f"select tx_id, tx_ts, emp_name, account_policy, merchant, mcc_name, total from transactions where tx_id in ({','.join('?'*len(ids))}) order by tx_ts", list(ids))
    df["emp_name"] = df.emp_name.map(mask); return df

def get_context(tx_id, n=20) -> dict:
    t = q("select * from transactions where tx_id=?", [tx_id]).iloc[0]
    recent = q("""select t.tx_id, t.tx_ts, t.account_policy, t.merchant, t.mcc_name, t.merchant_addr, t.total, coalesce((select list(distinct rule_id) from flags f where f.tx_id=t.tx_id), []) rules
                  from tx_active t where emp_id=? and tx_id<>? order by abs(epoch(tx_ts)-epoch(?)) limit ?""", [int(t.emp_id), tx_id, t.tx_ts, n])
    peer_pit = peer_from_features(tx_id)  # same point-in-time numbers the model sees; fall back to full-period SQL if the table is missing
    peer = q("""select account_policy, mcc_name, count(*) n, median(total) median, quantile_cont(total,0.9) p90, round(100.0*sum(case when total < ? then 1 else 0 end)/count(*),1) percentile_of_this
                from tx_active where account_policy=? and mcc_name=? and total>0 group by 1,2""", [float(t.total), t.account_policy, t.mcc_name]) if peer_pit is None else None
    access = q("select access_ts, gate, event, direction from access_logs where emp_id=? and cast(access_ts as date)=? order by access_ts", [int(t.emp_id), t.tx_date])
    hist = q(f"""with {_LATEST} select count(distinct f.tx_id) flagged_tx, count(distinct case when l.decision='violation' then f.tx_id end) violations, count(distinct case when l.decision='ok' then f.tx_id end) cleared
                 from flags f join transactions t using(tx_id) left join latest l on l.tx_id=f.tx_id and l.rule_id=f.rule_id where t.emp_id=?""", [int(t.emp_id)]).iloc[0].to_dict()
    peer_out = peer_pit if peer_pit is not None else (dict(peer.iloc[0].to_dict(), point_in_time=False) if len(peer) else None)
    return dict(recent_tx=recent, peer=peer_out, access_same_day=access,
                trip=dict(type=t.trip_type, start=t.trip_start, end=t.trip_end) if t.trip_type else None,
                leave=dict(type=t.leave_type, hours=t.leave_hours) if t.is_leave else None, holiday=bool(t.is_holiday), history=hist)

def get_profile(tx_id) -> dict:
    """What the three case charts need, all point-in-time (only rows before this tx's tx_ts):
    amount: this user's and the peer group's (account_policy × mcc_name) past amount quantiles;
    weekly: 13 weeks ending at the tx date — flagged tx and confirmed violations (latest decision 'violation', same definition as get_context.history)."""
    t = q("select emp_id, tx_ts, tx_date, total, account_policy, mcc_name from transactions where tx_id=?", [tx_id]).iloc[0]
    Q = "count(*) n, quantile_cont(total,0.25) p25, quantile_cont(total,0.5) p50, quantile_cont(total,0.75) p75, quantile_cont(total,0.9) p90"
    user = q(f"select {Q} from tx_active where emp_id=? and tx_ts<? and total>0", [int(t.emp_id), t.tx_ts]).iloc[0].to_dict()
    peer = q(f"select {Q} from tx_active where account_policy=? and mcc_name=? and tx_ts<? and total>0", [t.account_policy, t.mcc_name, t.tx_ts]).iloc[0].to_dict()
    for d in (user, peer):
        d["n"] = int(d["n"]); d.update({k: (None if pd.isna(d[k]) else float(d[k])) for k in ("p25", "p50", "p75", "p90")})
    weekly = q(f"""with {_LATEST},
      weeks as (select range as week_start from range(date_trunc('week', ?::date) - interval 12 week, date_trunc('week', ?::date) + interval 1 day, interval 1 week)),
      hits as (select date_trunc('week', t.tx_date) week_start, count(distinct f.tx_id) flagged,
                      count(distinct case when l.decision='violation' then f.tx_id end) violations
               from flags f join tx_active t using(tx_id) left join latest l on l.tx_id=f.tx_id and l.rule_id=f.rule_id
               where t.emp_id=? and t.tx_ts<? and t.tx_date >= date_trunc('week', ?::date) - interval 12 week group by 1)
      select cast(w.week_start as date) week_start, coalesce(h.flagged,0) flagged, coalesce(h.violations,0) violations
      from weeks w left join hits h using(week_start) order by 1""", [t.tx_date, t.tx_date, int(t.emp_id), t.tx_ts, t.tx_date])
    return dict(amount=dict(this=float(t.total), user=user, peer=peer), weekly=weekly)

# ---------- reviews ----------
def create_review(tx_id, rule_id, decision, reason_code, memo, reviewer) -> dict:
    assert decision in ("violation", "ok", "hold"), decision
    rid = uuid.uuid4().hex[:12]; now = dt.datetime.now()
    c = con()
    c.execute("update reviews set superseded_by=? where tx_id=? and coalesce(rule_id,'')=coalesce(?,'') and superseded_by is null", [rid, tx_id, rule_id]).fetchall()
    c.execute("insert into reviews values (?,?,?,?,?,?,?,?,NULL)", [rid, tx_id, rule_id, decision, reason_code, memo, reviewer, now]).fetchall()
    return dict(review_id=rid, tx_id=tx_id, rule_id=rule_id, decision=decision, reason_code=reason_code, memo=memo, reviewer=reviewer, created_at=now)

def bulk_review(tx_ids, rule_id, decision, reason_code, reviewer) -> int:
    for t in tx_ids: create_review(int(t), rule_id, decision, reason_code, "", reviewer)
    return len(tx_ids)

def get_reviews(tx_id) -> pd.DataFrame:
    return q("select review_id, rule_id, decision, reason_code, memo, reviewer, created_at, superseded_by is not null superseded from reviews where tx_id=? order by created_at desc", [tx_id])

def get_hit_rates(date_from=None, date_to=None) -> pd.DataFrame: return get_summary(date_from, date_to)

def log_event(reviewer, event, payload=None):
    con().execute("insert into ui_events values (?,?,?,?)", [dt.datetime.now(), reviewer, event, json.dumps(payload, ensure_ascii=False, default=str) if payload else None]).fetchall()



# ---------- conclusion-first headlines (two lines per rule: what / numbers) ----------
def evidence_headline(rule_id, ev: dict, t: dict) -> tuple[str, str]:
    g = lambda k, d="": ev.get(k, d)
    won = lambda v: f"{v:,.0f}원" if isinstance(v, (int, float)) else str(v)
    H = {"R01": lambda: (f"휴일({g('weekday')}) 사용", f"{g('date')} · {g('mcc')} · {won(g('total'))}"),
         "R02": lambda: (f"휴가일 {str(g('time'))[:5]} 사용", f"{g('leave_type')} {g('leave_hours')}h · {g('mcc')}"),
         "R03": lambda: (f"같은 가게에서 {g('window_min')}분 안에 {g('count_in_window')}건 결제", f"합계 {won(g('group_total'))} · {g('merchant')}"),
         "R04": lambda: (f"식당·카페에 {won(g('total'))} 단위금액 결제 (선결제 의심)", f"적요: {g('memo')}"),
         "R05": lambda: (f"집 근처({g('home_sigungu')})에서 사용", f"근무지 {g('work_sigungu')} · {str(g('time'))[:5]} · {g('mcc')}"),
         "R06": lambda: ({"same_person": f"{g('window_min')}분 안에 두 지역에서 결제", "named_attendee_elsewhere": "적요의 동석자가 같은 시각 다른 지역에서 결제", "counterpart": "다른 거래의 동석자로 적혔으나 다른 지역에 있었음"}.get(g('kind'), "동시간 다른 장소"), f"{g('this_sigungu')} ↔ {g('other_sigungu')}"),
         "R07": lambda: (f"{g('trip_type')} 중 출장지 밖({g('merchant_sido')})에서 사용", f"출장 {g('trip')} · {g('mcc')} · {won(g('total'))}"),
         "R08": lambda: (f"금지 업종 {g('mcc')}", f"계정 {g('account')} · {g('weekday')} {str(g('time'))[:5]} · {won(g('total'))}"),
         "R09": lambda: (f"주유 같은 날 {g('same_day_count') or 1}회 / 14일 {g('count_in_14d') or 1}회", f"기준 하루 {g('per_day')}회 · 14일 {g('per_window')}회"),
         "R10": lambda: (f"증빙 필수 업종({g('mcc')})인데 증빙 없음", f"{won(g('total'))} · 계정 {g('account')}"),
         "R11": lambda: ("해외출장 중 식사를 출장비 외 계정으로" if g('reason') == 'overseas_trip_meal_not_trip_account' else f"{g('mcc')}을 접대비 아닌 계정으로", f"계정 {g('account')}"),
         "R12": lambda: (f"사옥 입문 {g('minutes_before_purchase')}분 뒤 {g('merchant_sido')}에서 결제 (카드 대여 의심)", f"같은 패턴 {g('repeat_count')}회 · 근무지 {g('work_sido')}"),
         "R13": lambda: (f"개인물품 의심 (신호 {g('score')}/4)", f"키워드 {'O' if g('memo_keyword') else 'X'} · 쇼핑업종 {'O' if g('shopping_mcc') else 'X'} · 심야/휴일 {'O' if g('off_hours') else 'X'} · 증빙 {'O' if g('has_attachment') else 'X'}"),
         "R14": lambda: (f"{g('trip_type')} 중 식사를 카드로 결제", f"출장 {g('trip')} · 계정 {g('account')} · {won(g('total'))}"),
         "R15": lambda: (f"출장 종료 {g('days_before_end')}일 전에 복귀 교통편", f"출장 {g('trip')} · 이후 출장지 소비 없음"),
         "R16": lambda: (f"동료 중앙값의 {g('ratio')}배 금액", f"{g('peer_group')} 중앙값 {won(g('peer_median'))} vs {won(g('total'))}"),
         "R17": lambda: (f"자택방문교통비인데 경로 밖({g('merchant_sido')})", f"주거지 {g('home_sido')} · 근무지 {g('work_sido')} · {g('mcc')}"),
         "R18": lambda: (f"승인자 집 근처({g('approver_sigungu')}) 가맹점", f"{str(g('time'))[:5]} · {g('mcc')} · {won(g('total'))}"),
         "R21": lambda: (f"고액 식사 {won(g('total'))}, 참석 {g('attendees_in_memo') or '?'}명 (페이백 후보)", f"적요: {g('memo')}")}
    try: return H.get(rule_id[:3], lambda: (RULE_NAME.get(rule_id, rule_id), json.dumps(ev, ensure_ascii=False)))()
    except Exception: return (RULE_NAME.get(rule_id, rule_id), json.dumps(ev, ensure_ascii=False))

def get_policy(account):
    df = q("select account, description, dos, donts, required_evidence from policy_accounts where account=?", [account])
    return df.iloc[0].to_dict() if len(df) else None

def get_day_timeline(tx_id) -> pd.DataFrame:
    t = q("select emp_id, tx_date from transactions where tx_id=?", [tx_id]).iloc[0]
    return q("""
      select tx_ts ts, '카드' kind, merchant || ' · ' || coalesce(mcc_name,'') what, sigungu_of(merchant_addr) place, total amount, tx_id = ? focal
      from tx_active t where emp_id=? and tx_date=? and not time_is_dummy
      union all
      select access_ts, '출입', gate || ' · ' || event, site, null, false from access_logs where emp_id=? and cast(access_ts as date)=?
      order by 1""", [tx_id, int(t.emp_id), t.tx_date, int(t.emp_id), t.tx_date])

def review_transaction(tx_id, decision, reason_code, memo, reviewer) -> int:
    """Transaction-level verdict: recorded once per flagged rule so per-rule hit rates stay computable."""
    rules = q("select distinct rule_id from flags where tx_id=?", [tx_id]).rule_id.tolist()
    if not rules:  # unflagged tx (random / model queue rows): one transaction-level review with rule_id NULL
        create_review(tx_id, None, decision, reason_code, memo, reviewer); return 1
    for r in rules: create_review(tx_id, r, decision, reason_code, memo, reviewer)
    return len(rules)

def next_unreviewed(after_tx_id, queue_period=None, **filters):
    if queue_period:
        ids = list_queue(queue_period[0], queue_period[1], review_status="unreviewed", page_size=500, **{k: v for k, v in filters.items() if k in ("sources", "rule_ids", "depts", "min_total", "sort", "synthetic_only")}).tx_id.tolist()
    else:
        ids = list_flags(review_status="unreviewed", page_size=500, **filters).tx_id.tolist()
    if after_tx_id in ids:
        i = ids.index(after_tx_id); return ids[i + 1] if i + 1 < len(ids) else None
    return ids[0] if ids else None

def today_count(reviewer) -> int:
    return int(q("select count(distinct tx_id) from reviews where reviewer=? and cast(created_at as date)=current_date", [reviewer]).iloc[0, 0])


# ---------- policy citation: which written rule this flag violates ----------
_MCC_KEYS = {"주점": ["주점", "유흥"], "유흥주점": ["유흥", "주점"], "단란주점": ["주점", "유흥"], "노래방": ["노래", "유흥"], "골프장": ["골프"], "골프연습장": ["골프"],
             "안마": ["안마", "마사지"], "백화점": ["백화점", "개인"], "슈퍼마켓.마트": ["마트", "개인"], "인터넷상거래": ["개인용품", "개인"], "편의점": ["개인"]}
def policy_citation(rule_id, t: dict) -> str:
    """Return the sentence from the account's Don'ts that matches this transaction's merchant type; otherwise the rule's default policy_ref."""
    acct = t.get("account_policy"); mcc = str(t.get("mcc_name") or "")
    if rule_id[:3] in ("R08", "R11", "R10", "R13") and acct:
        pol = get_policy(acct)
        if pol:
            keys = _MCC_KEYS.get(mcc, []) + ([mcc] if mcc else [])
            for line in (pol["donts"] or "").split("\n"):
                if any(k and k in line for k in keys):
                    return f"{acct} 규정 Don'ts: “{line.strip()[:60]}”"
    return RULES.get(rule_id, {}).get("policy_ref", "")

# ---------- precedents: similar disciplinary cases (now) and similar reviewed transactions (later) ----------

_RULE_W = None
def rule_weights() -> dict:
    """IDF-style weight per rule: common rules (e.g. R16 amount outlier) count less than rare, specific ones."""
    global _RULE_W
    if _RULE_W is None:
        import math
        df = q("select rule_id, count(distinct tx_id) n from flags group by 1"); total = q("select count(distinct tx_id) from flags").iloc[0, 0] or 1
        _RULE_W = {r.rule_id: math.log(1 + total / max(r.n, 1)) for r in df.itertuples()}
    return _RULE_W

def get_precedents(tx_id, k=3) -> dict:
    """Rank precedents by weighted-Jaccard overlap of flagged-rule sets (weights = rule rarity) with small bonuses for same account / mcc.
    Returns overlap and difference as rule ids so the UI can show '겹치는 점 / 다른 점'. Empty when nothing overlaps."""
    if not con().execute("select count(*) from information_schema.tables where table_name='precedents'").fetchall()[0][0]:
        return dict(cases=[], reviews=[], summary=dict(n=0, violation=0, ok=0))
    t = q("select account_policy, mcc_name, total from transactions where tx_id=?", [tx_id]).iloc[0]
    tx_rules = set(q("select distinct rule_id from flags where tx_id=?", [tx_id]).rule_id)
    if not tx_rules: return dict(cases=[], reviews=[], summary=dict(n=0, violation=0, ok=0))
    W = rule_weights(); w = lambda rs: sum(W.get(r, 1.0) for r in rs)
    pre = q("select * from precedents")
    out = {"case": [], "review": []}
    for p in pre.itertuples():
        pr = set(list(p.rule_ids) if p.rule_ids is not None else []); inter = tx_rules & pr
        if not inter: continue
        score = w(inter) / w(tx_rules | pr) + 0.1 * (p.account == t.account_policy) + 0.1 * (p.mcc_group == t.mcc_name)
        out[p.kind].append(dict(precedent_id=p.precedent_id, kind=p.kind, title=p.title, summary=p.summary, cues=list(p.cues) if p.cues is not None else [], outcome=p.outcome, source=p.source,
                                score=round(score, 3), overlap=sorted(inter), only_in_precedent=sorted(pr - tx_rules), only_in_tx=sorted(tx_rules - pr)))
    num = lambda pid: int(pid.split(":")[1]) if pid.split(":")[1].isdigit() else 0
    for kind in out: out[kind].sort(key=lambda d: (-d["score"], num(d["precedent_id"])))
    rv = out["review"]
    return dict(cases=out["case"][:k], reviews=rv[:k],
                summary=dict(n=len(rv), violation=sum(r["outcome"] == "violation" for r in rv), ok=sum(r["outcome"] == "ok" for r in rv)))


# ---------- feature table hooks ----------
def _has_table(name) -> bool:
    return con().execute("select count(*) from information_schema.tables where table_name=?", [name]).fetchall()[0][0] > 0

def peer_from_features(tx_id):
    """Peer comparison from tx_features (point-in-time, excludes this tx). None if table/row missing or no prior peers."""
    if not _has_table("tx_features"): return None
    df = q("""select t.account_policy, t.mcc_name, f.acct_mcc__all__n_tx n, f.acct_mcc__all__median_total median, f.acct_mcc__all__p90_total p90, f.acct_mcc__all__amount_pctile percentile_of_this
              from tx_features f join transactions t using(tx_id) where f.tx_id=?""", [tx_id])
    if not len(df) or pd.isna(df.n.iloc[0]) or df.n.iloc[0] == 0: return None
    r = df.iloc[0].to_dict(); r["n"] = int(r["n"]); r["point_in_time"] = True; return r



# ---------- model score hooks ----------
def get_score(tx_id) -> dict | None:
    if not _has_table("tx_score"): return None
    df = q("select score, model_version, top_features, score_learned, learned_name, top_features_learned from tx_score where tx_id=?", [tx_id])
    if not len(df): return None
    r = df.iloc[0].to_dict()
    r["top_features"] = json.loads(r["top_features"] or "[]"); r["top_features_learned"] = json.loads(r["top_features_learned"] or "[]")
    from models.base import DEMO_DISCLAIMER; r["disclaimer"] = DEMO_DISCLAIMER; return r

def top_unflagged_by_score(n=50) -> pd.DataFrame:
    """Transactions no rule caught but the learned model scores high: the third queue entrance and discovery input."""
    if not _has_table("tx_score"): return pd.DataFrame()
    df = q("""select t.tx_id, t.tx_ts, t.emp_name, t.dept, t.account_policy, t.merchant, t.mcc_name, t.total, s.score_learned, s.top_features_learned
              from tx_score s join tx_active t using(tx_id) where t.tx_id not in (select tx_id from flags) and not t.is_synthetic and s.score_learned is not null
              order by s.score_learned desc, t.tx_id limit ?""", [n])
    df["emp_name"] = df.emp_name.map(mask); return df


# ---------- review queue: rule rows + model top-M + random sample, with provenance ----------
def build_queue(period_from, period_to, p_random=0.10, m_model=20, seed=42, min_random=10, force=False) -> dict:
    """Build the list auditors work from for one period. Replaces the period's rows. Refuses to rebuild over existing reviews unless force
    (then reviewed rows are kept with their original source/prob and excluded from the new pools)."""
    import duckdb as _d
    c = con(); pf, pt = str(period_from), str(period_to)
    kept = q("""select qu.* from queue qu where qu.period_from=? and qu.period_to=? and qu.tx_id in (select tx_id from reviews where superseded_by is null)""", [pf, pt])
    if len(kept) and not force: raise ValueError(f"{len(kept)} queued tx already have reviews in {pf}~{pt}; pass force=True to rebuild (reviewed rows are kept)")
    kept_ids = [int(x) for x in kept.tx_id] if len(kept) else [-1]
    ph = ",".join(str(i) for i in kept_ids)
    has_score = _has_table("tx_score")
    rule_order = "coalesce(sc.score, 0) desc, n_rules desc, t.total desc, t.tx_id" if has_score else "n_rules desc, t.total desc, t.tx_id"
    score_join = "left join tx_score sc on sc.tx_id = t.tx_id" if has_score else ""
    rule = q(f"""select t.tx_id, row_number() over (order by {rule_order}) rk from tx_active t join (select tx_id, count(distinct rule_id) n_rules from flags group by 1) f using(tx_id) {score_join}
                 where t.tx_date between ? and ? and t.tx_id not in ({ph})""", [pf, pt])
    model = q(f"""select t.tx_id, row_number() over (order by sc.score_learned desc, t.tx_id) rk from tx_active t join tx_score sc on sc.tx_id=t.tx_id
                  where t.tx_date between ? and ? and not t.is_synthetic and sc.score_learned is not null and t.tx_id not in (select tx_id from flags) and t.tx_id not in ({ph})
                  order by rk limit ?""", [pf, pt, int(m_model)]) if has_score and m_model > 0 else pd.DataFrame(columns=["tx_id", "rk"])
    excl = ",".join(str(int(x)) for x in list(model.tx_id) + kept_ids) or "-1"
    pool_n = q(f"""select count(*) from tx_active t where t.tx_date between ? and ? and not t.is_synthetic and t.tx_id not in (select tx_id from flags) and t.tx_id not in ({excl})""", [pf, pt]).iloc[0, 0]
    n_kept_random = int((kept.queue_source == "random").sum()) if len(kept) else 0
    n_random = int(min(pool_n, max(round(p_random * (len(rule) + int((kept.queue_source == "rule").sum() if len(kept) else 0))), min_random) - n_kept_random)); n_random = max(n_random, 0)
    rnd = q(f"""select t.tx_id, row_number() over (order by hash(cast(t.tx_id as varchar) || '|' || ?), t.tx_id) rk from tx_active t
                where t.tx_date between ? and ? and not t.is_synthetic and t.tx_id not in (select tx_id from flags) and t.tx_id not in ({excl})
                order by rk limit ?""", [str(seed), pf, pt, n_random])
    qid = uuid.uuid4().hex[:12]; now = dt.datetime.now()
    params = dict(p_random=p_random, m_model=m_model, seed=seed, min_random=min_random, n_rule=len(rule), n_model=len(model), n_random=len(rnd), n_pool_unflagged=int(pool_n),
                  order_by="score" if has_score else "n_rules", duckdb_version=_d.__version__, kept_reviewed=int(len(kept)))
    rows = [dict(queue_id=qid, period_from=pf, period_to=pt, tx_id=int(r.tx_id), queue_source="rule", selection_prob=1.0, rank_in_source=int(r.rk), built_at=now, seed=seed, params=json.dumps(params)) for r in rule.itertuples()]
    rows += [dict(queue_id=qid, period_from=pf, period_to=pt, tx_id=int(r.tx_id), queue_source="model", selection_prob=1.0, rank_in_source=int(r.rk), built_at=now, seed=seed, params=json.dumps(params)) for r in model.itertuples()]
    prob = (len(rnd) / pool_n) if pool_n else 1.0
    rows += [dict(queue_id=qid, period_from=pf, period_to=pt, tx_id=int(r.tx_id), queue_source="random", selection_prob=float(prob), rank_in_source=int(r.rk), built_at=now, seed=seed, params=json.dumps(params)) for r in rnd.itertuples()]
    c.execute("delete from queue where period_from=? and period_to=? and tx_id not in (" + ph + ")", [pf, pt]).fetchall()
    if rows:
        df = pd.DataFrame(rows); c.register("qdf", df); c.execute("insert into queue select * from qdf").fetchall(); c.unregister("qdf")
    return dict(queue_id=qid, period_from=pf, period_to=pt, n_rule=len(rule), n_model=len(model), n_random=len(rnd), n_pool_unflagged=int(pool_n), kept_reviewed=int(len(kept)))

def list_queue_periods() -> pd.DataFrame:
    if not _has_table("queue"): return pd.DataFrame(columns=["period_from", "period_to", "n", "built_at"])
    return q("select period_from, period_to, count(*) n, max(built_at) built_at from queue group by 1,2 order by 1 desc")

def list_queue(period_from, period_to, sources=None, rule_ids=None, depts=None, min_total=None, review_status=None, sort="source", page=1, page_size=100, synthetic_only=None) -> pd.DataFrame:
    has_score = _has_table("tx_score")
    score_sel = "sc.score, sc.score_learned," if has_score else "null::double score, null::double score_learned,"
    score_join = "left join tx_score sc on sc.tx_id = t.tx_id" if has_score else ""
    where, p = ["qu.period_from=? and qu.period_to=?"], [str(period_from), str(period_to)]
    if sources: where.append(f"qu.queue_source in ({','.join('?'*len(sources))})"); p += list(sources)
    if rule_ids: where.append(f"list_has_any(coalesce(fl.rules, []), [{','.join('?'*len(rule_ids))}])"); p += list(rule_ids)
    if depts: where.append(f"t.dept in ({','.join('?'*len(depts))})"); p += list(depts)
    if min_total: where.append("t.total >= ?"); p.append(min_total)
    if synthetic_only is not None: where.append("t.is_synthetic = ?"); p.append(synthetic_only)
    if review_status == "unreviewed": where.append("rv.decision is null")
    elif review_status == "reviewed": where.append("rv.decision is not null")
    elif review_status == "violation": where.append("rv.decision = 'violation'")
    order = {"source": "case qu.queue_source when 'rule' then 0 when 'model' then 1 else 2 end, qu.rank_in_source, t.tx_id", "total": "t.total desc, t.tx_id",
             "rules": "n_rules desc, t.total desc, t.tx_id", "date": "t.tx_ts desc, t.tx_id", "score": "score desc nulls last, t.tx_id", "learned": "score_learned desc nulls last, t.tx_id"}[sort]
    df = q(f"""with {_LATEST},
      fl as (select tx_id, list(distinct rule_id order by rule_id) rules, count(distinct rule_id) n_rules, max(case severity when 'violation' then 2 else 1 end) sev from flags group by 1),
      rv as (select tx_id, max(decision) decision from latest group by 1)
      select qu.queue_source, qu.selection_prob, qu.rank_in_source, t.tx_id, t.tx_ts, t.emp_id, t.emp_name, t.dept, t.rank, t.account_policy, t.merchant, t.mcc_name, t.total, t.is_synthetic,
             coalesce(fl.rules, []) rules, coalesce(fl.n_rules, 0) n_rules, coalesce(fl.sev, 0) sev, coalesce(rv.decision, 'unreviewed') review_status, {score_sel} 1 one
      from queue qu join tx_active t using(tx_id) left join fl using(tx_id) left join rv using(tx_id) {score_join}
      where {' and '.join(where)} order by {order} limit ? offset ?""", p + [page_size, (page - 1) * page_size])
    df["emp_name"] = df.emp_name.map(mask); return df

def get_queue_summary(period_from, period_to) -> pd.DataFrame:
    """Per-source counts and hit rates. For random rows est_missed = violation rate × unflagged pool size — the first measurement of what rules miss."""
    df = q(f"""with {_LATEST}, rv as (select tx_id, max(decision) decision from latest group by 1)
      select qu.queue_source source, count(*) n, count(rv.decision) reviewed,
             sum(case when rv.decision='violation' then 1 else 0 end) violation, sum(case when rv.decision='ok' then 1 else 0 end) ok, sum(case when rv.decision='hold' then 1 else 0 end) hold,
             round(100.0*sum(case when rv.decision='violation' then 1 else 0 end)/nullif(sum(case when rv.decision in ('violation','ok') then 1 else 0 end),0),1) hit_rate_pct,
             min(qu.selection_prob) selection_prob, max(qu.params) params
      from queue qu left join rv using(tx_id) where qu.period_from=? and qu.period_to=? group by 1 order by case qu.queue_source when 'rule' then 0 when 'model' then 1 else 2 end""", [str(period_from), str(period_to)])
    if len(df):
        pool = json.loads(df.params.iloc[0]).get("n_pool_unflagged", 0)
        df["est_missed"] = [round(pool * (r.violation / r.reviewed)) if r.source == "random" and r.reviewed else None for r in df.itertuples()]
    return df.drop(columns=["params"]) if len(df) else df
