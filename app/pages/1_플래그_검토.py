import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import streamlit as st, pandas as pd
from app import service as s

st.set_page_config(page_title="플래그 검토", layout="wide")
st.markdown("<style>.block-container{padding-top:1.2rem} h1{font-size:1.5rem!important} .sub{color:#777;font-size:.9rem} .cite{color:#8a6d3b;font-size:.85rem}</style>", unsafe_allow_html=True)
DOT = {"violation": "🔴", "advisory": "⚪"}
rules = s.list_rules()
reviewer = st.sidebar.text_input("검토자 이름", value=st.session_state.get("reviewer", ""))
st.session_state["reviewer"] = reviewer

# ---- queue mode: the list auditors work from (rule rows + model top-M + random sample), when a queue has been built ----
periods = s.list_queue_periods()
queue_mode = st.sidebar.toggle("큐 모드 (규칙 + 모델 + 무작위 표본)", value=True) if len(periods) else False
qp = None; q_sources = None
if queue_mode:
    labels_p = [f"{r.period_from}~{r.period_to} · {r.n:,}건" for r in periods.itertuples()]
    pick = st.sidebar.selectbox("큐 기간", range(len(labels_p)), format_func=lambda i: labels_p[i]); qp = (str(periods.period_from.iloc[pick]), str(periods.period_to.iloc[pick]))
    q_sources = st.sidebar.multiselect("출처", ["rule", "model", "random"], default=["rule", "model", "random"], format_func=lambda v: {"rule": "규칙에 걸림", "model": "🧠 모델 추천(규칙 밖)", "random": "🎲 무작위 표본"}[v])
st.sidebar.header("필터")
sel_rules = st.sidebar.multiselect("규칙", rules.rule_id.tolist(), format_func=lambda r: f"{DOT[s.rule_tier(r)]} {r[:3]} {s.RULE_NAME[r]}")
status = st.sidebar.selectbox("검토 상태", ["unreviewed", None, "reviewed", "violation"], format_func=lambda v: {None: "전체", "unreviewed": "미검토", "reviewed": "검토됨", "violation": "위반 확정"}[v])
min_total = st.sidebar.number_input("금액 이상", min_value=0, value=0, step=10000)
SORTS = ({"source": "큐 순서(규칙→모델→무작위)"} if queue_mode else {}) | {"rules": "걸린 규칙 수", "total": "금액", "date": "날짜"}
if s._has_table("tx_score"): SORTS.update({"score": "기준선 점수(규칙 수×금액)", "learned": "학습 모델 점수 (시연용)"})
sort = st.sidebar.selectbox("정렬", list(SORTS), format_func=lambda v: SORTS[v])
syn = st.sidebar.selectbox("데이터", [None, False, True], format_func=lambda v: {None: "전체", False: "실데이터만", True: "합성(테스트)만"}[v])
page = st.sidebar.number_input("페이지 (100건씩)", min_value=1, value=1)
F = dict(rule_ids=sel_rules or None, min_total=min_total or None, sort=sort, synthetic_only=syn)

# ---------- A. list ----------
df = s.list_queue(qp[0], qp[1], sources=q_sources or None, review_status=status, page=page, page_size=100, **F) if queue_mode else s.list_flags(review_status=status, page=page, page_size=100, **F)
c1, c2 = st.columns([4, 1]); c1.title("플래그 검토")
c2.markdown(f"<p class='sub' style='text-align:right;padding-top:1.4rem'>이 목록 {len(df)}건 · 오늘 처리 {s.today_count(reviewer) if reviewer else 0}건</p>", unsafe_allow_html=True)
def badge(r):
    src = getattr(r, "queue_source", "rule")
    if src == "random": return "🎲 무작위"
    if src == "model": return "🧠 모델"
    return ("🔴" if r.sev == 2 else "⚪") + f" ×{r.n_rules}"
show = pd.DataFrame({"": [badge(r) for r in df.itertuples()], "일시": df.tx_ts.dt.strftime("%m-%d %H:%M"), "사용자": df.emp_name, "직급": df["rank"],
                     "가맹점": df.merchant, "업종": df.mcc_name, "금액": df.total.map(lambda v: f"{v:,.0f}"), "계정": df.account_policy,
                     **({"학습점수": df.score_learned.map(lambda v: f"{v:.2f}" if pd.notna(v) else "")} if "score_learned" in df and df.score_learned.notna().any() else {}),
                     "상태": df.review_status.map({"unreviewed": "", "violation": "위반", "ok": "아님", "hold": "보류"}), "T": df.is_synthetic.map({True: "T", False: ""})})
st.caption("🔴 규정 근거가 있는 규칙에 걸림 (확인 대상) · ⚪ 통계·가설 규칙만 걸림 (참고) · ×n 걸린 규칙 수" + (" · 🧠 모델: 규칙엔 안 걸렸지만 학습 점수 상위 · 🎲 무작위: 안 걸린 거래의 제비뽑기 표본 — 대부분 '아님'이 정상이며, 여기서 나오는 '위반'이 규칙이 놓친 것을 알려줍니다. 규칙 필터는 규칙 행에만 적용됩니다." if queue_mode else ""))
ev = st.dataframe(show, width='stretch', hide_index=True, on_select="rerun", selection_mode="single-row", height=280, key="flags_table")
sel = ev.selection.rows if ev and ev.selection else []
if sel:
    picked = int(df.tx_id.iloc[sel[0]])
    if picked != st.session_state.get("tx_id"):
        st.session_state["tx_id"] = picked; st.session_state.pop("pending_ok", None); st.session_state.pop("saved_msg", None); s.log_event(reviewer, "open_case", {"tx_id": picked})
tx_id = st.session_state.get("tx_id")
if tx_id is None:
    st.info("한 줄의 맨 왼쪽 체크박스를 누르면 아래에 판정 화면이 열립니다."); st.stop()
t = s.get_transaction(tx_id); evs = s.get_evidence(tx_id)

def go_next():
    nxt = s.next_unreviewed(tx_id, queue_period=qp, sources=q_sources or None, **F) if queue_mode else s.next_unreviewed(tx_id, **F); st.session_state["tx_id"] = int(nxt) if nxt else None
    st.session_state.pop("pending_ok", None); st.session_state.pop("saved_msg", None); st.rerun()
def decide(decision, reason="", memo=""):
    n = s.review_transaction(tx_id, decision, reason, memo, reviewer); s.log_event(reviewer, "review", {"tx_id": tx_id, "decision": decision})
    st.session_state["saved_msg"] = f"저장됨: {dict(violation='위반', ok='아님', hold='보류')[decision]} " + (f"(규칙 {n}개에 기록)" if evs else "(거래 단위 기록 — 걸린 규칙 없음)"); st.session_state.pop("pending_ok", None); st.rerun()

# ---------- B. one case ----------
st.divider()
st.markdown(f"#### #{tx_id} · {t['tx_ts']:%m-%d(%a) %H:%M} · {t['emp_name']} ({t['dept']} {t['rank']}) · {t['merchant']} [{t['mcc_name']}]")
st.markdown(f"<p class='sub'>{t['total']:,.0f}원 · {t['account_policy']}" + (f" · 적요 “{t['memo']}”" if t.get("memo") else "") + f" · 증빙 {'있음' if t['has_attachment'] else '없음'}</p>", unsafe_allow_html=True)
sc = s.get_score(tx_id)
if sc and sc.get("score_learned") is not None and not pd.isna(sc["score_learned"]):
    st.markdown(f"<p class='sub'>학습 모델({sc['learned_name']}) 점수 <b>{sc['score_learned']:.2f}</b> · 이유: " + " · ".join(h for _, _, h in sc["top_features_learned"]) + f"<br><span style='color:#999'>{sc['disclaimer']}</span></p>", unsafe_allow_html=True)
left, right = st.columns([3, 1.3])
with left:
    st.markdown("**왜 걸렸나**")
    ctx = s.get_context(tx_id); p = ctx["peer"]
    if not evs: st.info("걸린 규칙 없음. 이 거래는 큐 출처(모델 추천 또는 무작위 표본)로 올라왔습니다. 거래 자체와 아래 정황을 보고 판단하세요.")
    for e in evs:
        head, detail = s.evidence_headline(e["rule_id"], e["evidence"], t); cite = s.policy_citation(e["rule_id"], t)
        a, b, c = st.columns([6, 1, 1])
        a.markdown(f"{DOT[e['severity']]} **{head}**  \n<span class='sub'>{detail} · {e['rule_id'][:3]} {e['rule_name']}</span>" + (f"  \n<span class='cite'>근거: {cite}</span>" if cite else ""), unsafe_allow_html=True)
        with b.popover("왜?", help="이 규칙이 무엇을 보는지"): st.write(s.rule_explain(e["rule_id"]))
        with c.popover("동료", help="같은 계정·업종에서 남들은 얼마 쓰나"):
            if p: st.write(f"{p['account_policy']} × {p['mcc_name']} {p['n']:,}건 · 중앙값 {p['median']:,.0f}원 · 상위 10% 경계 {p['p90']:,.0f}원 · 이 건 {t['total']:,.0f}원은 상위 {100-p['percentile_of_this']:.0f}% 지점" + (" (이 거래 이전 거래 기준, 모델과 같은 숫자)" if p.get("point_in_time") else " (전 기간 기준)"))
            else: st.write("비교할 집단이 없음 (같은 계정·업종 거래 30건 미만)")
    rel = [e["related_tx"].assign(규칙=e["rule_id"][:3]) for e in evs if len(e["related_tx"])]
    if rel:
        st.markdown("**함께 볼 거래** (분할 짝 · 동시간 상대 · 반복 패턴)")
        r = pd.concat(rel).drop_duplicates("tx_id")
        st.dataframe(pd.DataFrame({"규칙": r.규칙, "일시": pd.to_datetime(r.tx_ts).dt.strftime("%m-%d %H:%M"), "사용자": r.emp_name, "가맹점": r.merchant, "업종": r.mcc_name, "금액": r.total.map(lambda v: f"{v:,.0f}"), "계정": r.account_policy}),
                     hide_index=True, width='stretch', height=min(40 + 36 * len(r), 200))
    # ---- precedents chip: shown only when at least one case shares a rule ----
    pre = s.get_precedents(tx_id)
    if pre["cases"]:
        top = pre["cases"][0]
        with st.expander(f"📁 비슷한 징계사례 {len(pre['cases'])}건 · 가장 가까운: “{top['title']}”", expanded=False):
            st.caption("규칙이 겹치는 사례입니다. 사례가 있다는 것이 위반을 뜻하지는 않습니다. 겹치는 점과 다른 점을 함께 보세요.")
            for c in pre["cases"]:
                with st.container(border=True):
                    st.markdown(f"**{c['title']}** <span class='sub'>· {c['source']} · 유사도 {c['score']:.2f}</span>", unsafe_allow_html=True)
                    st.markdown(f"**무슨 일이었나** — {c['summary']}")
                    st.markdown("**무엇을 보고 적발했나** — " + " · ".join(c["cues"]))
                    a, b = st.columns(2)
                    a.markdown("**겹치는 점**  \n" + "  \n".join(f"● {r[:3]} {s.RULE_NAME.get(r, r)}" for r in c["overlap"]))
                    diff = [f"○ 사례에만: {r[:3]} {s.RULE_NAME.get(r, r)}" for r in c["only_in_precedent"]] + [f"○ 이 거래에만: {r[:3]} {s.RULE_NAME.get(r, r)}" for r in c["only_in_tx"]]
                    b.markdown("**다른 점**  \n" + ("  \n".join(diff) if diff else "없음"))
        if pre["summary"]["n"]:
            st.caption(f"비슷한 거래의 과거 판정: {pre['summary']['n']}건 중 위반 {pre['summary']['violation']} · 아님 {pre['summary']['ok']}")
with right:
    st.markdown("**판정**")
    if not reviewer: st.warning("왼쪽에 검토자 이름을 입력하세요.")
    if st.session_state.get("saved_msg"): st.success(st.session_state["saved_msg"])
    b1, b2 = st.columns(2)
    if b1.button("위반", type="primary", width='stretch', disabled=not reviewer): decide("violation")
    if b2.button("아님", width='stretch', disabled=not reviewer): st.session_state["pending_ok"] = True
    if st.session_state.get("pending_ok"):
        reason = st.selectbox("왜 아닌가요?", [c for c, _ in s.REASON_CODES], format_func=lambda c: dict(s.REASON_CODES)[c])
        memo = st.text_input("메모 (선택)")
        if st.button("아님으로 저장", width='stretch'): decide("ok", reason, memo)
    h1, h2 = st.columns(2)
    if h1.button("보류", width='stretch', disabled=not reviewer): decide("hold", "need_evidence")
    if h2.button("다음 건 →", width='stretch'): go_next()
    rv = s.get_reviews(tx_id)
    if len(rv): st.caption("이력: " + " · ".join(f"{r.decision}({r.reviewer}, {r.created_at:%m-%d %H:%M})" for r in rv.drop_duplicates(["decision", "reviewer"]).itertuples()))

# ---------- C. on demand ----------
with st.expander("정황 보기 — 그날 동선 · 출장/휴가 상태", expanded=False):
    badges = ["휴일" if ctx["holiday"] else "휴일 아님", f"휴가 {ctx['leave']['type']} {ctx['leave']['hours']}h" if ctx["leave"] else "휴가 아님",
              f"{ctx['trip']['type']} {ctx['trip']['start']}~{ctx['trip']['end']}" if ctx["trip"] else "출장 없음"]
    st.markdown("상태: " + " · ".join(badges))
    tl = s.get_day_timeline(tx_id)
    st.markdown("**그날 동선** (★ = 이 거래)")
    st.dataframe(pd.DataFrame({"": tl.focal.map({True: "★", False: ""}), "시각": tl.ts.dt.strftime("%H:%M"), "구분": tl.kind, "내용": tl.what, "장소": tl.place,
                               "금액": tl.amount.map(lambda v: f"{v:,.0f}" if pd.notna(v) else "")}), hide_index=True, width='stretch', height=min(40 + 36 * len(tl), 320))
with st.expander("배경 보기 — 이 사람 이력 · 규정 원문 · 최근 거래 · 원본 근거", expanded=False):
    h = ctx["history"]; pol = s.get_policy(t["account_policy"])
    st.markdown(f"**이 사람:** 걸림 {h['flagged_tx']}건 · 위반 {h['violations']}건 · 아님 {h['cleared']}건")
    if pol:
        c1, c2 = st.columns(2)
        c1.markdown(f"**{t['account_policy']} · 허용**  \n" + pol["dos"].replace("\n", "  \n")); c2.markdown(f"**{t['account_policy']} · 금지**  \n" + pol["donts"].replace("\n", "  \n"))
    r = ctx["recent_tx"]; st.markdown("**최근 거래 20건**"); st.dataframe(r.assign(규칙=r.rules.map(lambda l: " ".join(x[:3] for x in l))).drop(columns=["rules"]), hide_index=True, width='stretch')
    st.json({e["rule_id"]: e["evidence"] for e in evs}, expanded=False)
