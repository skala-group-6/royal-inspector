"""Service layer: everything the UI needs, as plain functions over DuckDB.
Streamlit calls these directly today; FastAPI will wrap the same functions later. No UI code here."""
from __future__ import annotations
import json, datetime as dt, uuid
from pathlib import Path
import duckdb, pandas as pd, yaml

DB = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"
CATALOG = Path(__file__).resolve().parents[1] / "rules" / "catalog.yaml"
RULE_CLASS = {"①규정": ["R01", "R02", "R08", "R10", "R11", "R18"], "②임계치": ["R03", "R04", "R05", "R06", "R09", "R16"],
              "③가설": ["R07", "R12", "R13", "R14", "R15", "R17", "R21"]}
REASON_CODES = [("preapproved", "사전 승인·품의 있음"), ("trip_extended", "출장 일정 변경·연장"), ("business_confirmed", "업무 관련성 확인됨"),
                ("data_error", "데이터 오류(주소·시간·계정)"), ("legit_mismatch", "정당한 불일치(환율·매입일·부분취소)"), ("duplicate_flag", "다른 플래그와 중복"),
                ("need_evidence", "증빙 요청 필요"), ("other", "기타")]

_con = None
def con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        _con = duckdb.connect(str(DB))
        _con.execute(open(CATALOG.parent / "macros.sql").read()).fetchall()
        _con.execute("""CREATE TABLE IF NOT EXISTS reviews(review_id VARCHAR, tx_id BIGINT, rule_id VARCHAR, decision VARCHAR, reason_code VARCHAR,
                        memo VARCHAR, reviewer VARCHAR, created_at TIMESTAMP, superseded_by VARCHAR)""").fetchall()
        _con.execute("CREATE TABLE IF NOT EXISTS ui_events(ts TIMESTAMP, reviewer VARCHAR, event VARCHAR, payload VARCHAR)").fetchall()
    return _con
def q(sql, params=None) -> pd.DataFrame: return con().execute(sql, params or []).df()
def mask(name): return name if not isinstance(name, str) or len(name) < 2 else name[0] + "*" * (len(name) - 2) + name[-1]
def rule_class(rid): return next((c for c, l in RULE_CLASS.items() if rid[:3] in l), "미분류")

# ---------- rules ----------
def list_rules() -> pd.DataFrame:
    cat = yaml.safe_load(open(CATALOG))["rules"]
    return pd.DataFrame([dict(rule_id=k, name=v["name"], rule_class=rule_class(k), data_ready=v["data_ready"], params=json.dumps(v["params"], ensure_ascii=False)) for k, v in cat.items()])
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
    order = {"total": "t.total desc, t.tx_id", "rules": "n_rules desc, t.total desc, t.tx_id", "date": "t.tx_ts desc, t.tx_id"}[sort]  # tx_id tiebreak: order must be deterministic across reruns
    status_filter = {"unreviewed": "having count(l.decision)=0", "reviewed": "having count(l.decision)>0", "violation": "having bool_or(l.decision='violation')", None: ""}[review_status]
    df = q(f"""with {_LATEST}
      select t.tx_id, t.tx_ts, t.emp_id, t.emp_name, t.dept, t.rank, t.account_policy, t.merchant, t.mcc_name, t.total, t.is_synthetic,
             list(distinct f.rule_id order by f.rule_id) rules, count(distinct f.rule_id) n_rules,
             max(case f.severity when 'high' then 3 when 'medium' then 2 else 1 end) sev,
             coalesce(max(l.decision), 'unreviewed') review_status
      from flags f join tx_active t using(tx_id) left join latest l on l.tx_id=f.tx_id and l.rule_id=f.rule_id
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
    peer = q("""select account_policy, mcc_name, count(*) n, median(total) median, quantile_cont(total,0.9) p90, round(100.0*sum(case when total < ? then 1 else 0 end)/count(*),1) percentile_of_this
                from tx_active where account_policy=? and mcc_name=? and total>0 group by 1,2""", [float(t.total), t.account_policy, t.mcc_name])
    access = q("select access_ts, gate, event, direction from access_logs where emp_id=? and cast(access_ts as date)=? order by access_ts", [int(t.emp_id), t.tx_date])
    hist = q(f"""with {_LATEST} select count(distinct f.tx_id) flagged_tx, count(distinct case when l.decision='violation' then f.tx_id end) violations, count(distinct case when l.decision='ok' then f.tx_id end) cleared
                 from flags f join transactions t using(tx_id) left join latest l on l.tx_id=f.tx_id and l.rule_id=f.rule_id where t.emp_id=?""", [int(t.emp_id)]).iloc[0].to_dict()
    return dict(recent_tx=recent, peer=(peer.iloc[0].to_dict() if len(peer) else None), access_same_day=access,
                trip=dict(type=t.trip_type, start=t.trip_start, end=t.trip_end) if t.trip_type else None,
                leave=dict(type=t.leave_type, hours=t.leave_hours) if t.is_leave else None, holiday=bool(t.is_holiday), history=hist)

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

def list_depts() -> list[str]: return q("select distinct dept from tx_active where dept is not null order by 1").dept.tolist()
