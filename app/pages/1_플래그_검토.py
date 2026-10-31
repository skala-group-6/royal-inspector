import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import streamlit as st, pandas as pd
from app import service as s

st.set_page_config(page_title="플래그 검토", layout="wide")
rules = s.list_rules()
reviewer = st.sidebar.text_input("검토자 이름", value=st.session_state.get("reviewer", ""), help="결정 기록에 남습니다")
st.session_state["reviewer"] = reviewer

# ---------- filters ----------
st.sidebar.header("필터")
sel_rules = st.sidebar.multiselect("규칙", rules.rule_id.tolist(), format_func=lambda r: f"{r[:3]} {s.RULE_NAME[r]}")
status = st.sidebar.selectbox("검토 상태", [None, "unreviewed", "reviewed", "violation"], format_func=lambda v: {None: "전체", "unreviewed": "미검토", "reviewed": "검토됨", "violation": "위반 확정"}[v])
min_total = st.sidebar.number_input("금액 이상", min_value=0, value=0, step=10000)
sort = st.sidebar.selectbox("정렬", ["rules", "total", "date"], format_func=lambda v: {"rules": "걸린 규칙 수", "total": "금액", "date": "날짜"}[v])
syn = st.sidebar.selectbox("데이터", [None, False, True], format_func=lambda v: {None: "전체", False: "실데이터만", True: "합성(테스트)만"}[v])
page_size = st.sidebar.selectbox("페이지 크기", [50, 100, 200], index=1)
page = st.sidebar.number_input("페이지", min_value=1, value=1)

df = s.list_flags(rule_ids=sel_rules or None, min_total=min_total or None, review_status=status, sort=sort, page=page, page_size=page_size, synthetic_only=syn)
st.title("플래그 검토")
st.caption(f"{len(df)}건 표시 (페이지 {page}). 거래 한 건을 보려면 그 줄 **맨 왼쪽의 체크박스**를 클릭하세요. 아래에 상세와 판정 버튼이 열립니다.")

show = df.assign(규칙=df.rules.map(lambda l: " ".join(r[:3] for r in l)), 금액=df.total.map(lambda v: f"{v:,.0f}"),
                 일시=df.tx_ts.dt.strftime("%m-%d %H:%M"), 합성=df.is_synthetic.map({True: "T", False: ""}))[
    ["tx_id", "일시", "emp_name", "dept", "rank", "account_policy", "merchant", "mcc_name", "금액", "규칙", "review_status", "합성"]].rename(
    columns={"emp_name": "사용자", "dept": "부서", "rank": "직급", "account_policy": "계정", "merchant": "가맹점", "mcc_name": "업종", "review_status": "상태"})
# Stable widget key + selected tx_id kept in session_state: the detail survives reruns (filter change, save) even if the table re-renders.
ev = st.dataframe(show, width='stretch', hide_index=True, on_select="rerun", selection_mode="single-row", height=380, key="flags_table")
sel = ev.selection.rows if ev and ev.selection else []
if sel:
    picked = int(df.tx_id.iloc[sel[0]])
    if picked != st.session_state.get("tx_id"):
        st.session_state["tx_id"] = picked; s.log_event(reviewer, "open_case", {"tx_id": picked})
tx_id = st.session_state.get("tx_id")
if tx_id is None:
    st.info("위 표에서 한 줄의 맨 왼쪽 체크박스를 클릭하면 여기에 상세가 열립니다."); st.stop()
t = s.get_transaction(tx_id)

# ---------- case detail ----------
st.divider()
st.subheader(f"거래 #{tx_id} — {t['tx_ts']:%Y-%m-%d %H:%M} · {t['emp_name']} ({t['dept']}, {t['rank']}) · {t['merchant']} · {t['mcc_name']} · {t['total']:,.0f}원 · {t['account_policy']}")
if t.get("memo"): st.caption(f"적요: {t['memo']}")
left, right = st.columns([3, 2])

with left:
    st.markdown("#### 걸린 규칙과 근거")
    evs = s.get_evidence(tx_id)
    for e in evs:
        with st.container(border=True):
            st.markdown(f"**{e['rule_id'][:3]} {e['rule_name']}** · {e['rule_class']} · 심각도 {e['severity']}")
            st.write(e["evidence_text"])
            if len(e["related_tx"]):
                st.caption("관련 거래"); st.dataframe(e["related_tx"], hide_index=True, width='stretch')
            with st.expander("원본 근거(JSON)"): st.json(e["evidence"])
    ctx = s.get_context(tx_id)
    st.markdown("#### 맥락")
    tabs = st.tabs(["같은 사람 최근 거래", "동료 비교", "당일 출입기록", "출장·휴가"])
    with tabs[0]:
        r = ctx["recent_tx"]; st.dataframe(r.assign(규칙=r.rules.map(lambda l: " ".join(x[:3] for x in l))).drop(columns=["rules"]), hide_index=True, width='stretch')
    with tabs[1]:
        p = ctx["peer"]
        if p: st.write(f"같은 계정·업종({p['account_policy']} × {p['mcc_name']}) {p['n']:,}건 중앙값 **{p['median']:,.0f}원**, 상위 10% 경계 {p['p90']:,.0f}원. 이 거래는 상위 **{100-p['percentile_of_this']:.0f}%** 지점.")
        else: st.write("비교 집단 없음")
    with tabs[2]:
        a = ctx["access_same_day"]; st.dataframe(a, hide_index=True, width='stretch') if len(a) else st.write("당일 출입기록 없음")
    with tabs[3]:
        st.write({"휴일": ctx["holiday"], "출장": ctx["trip"], "휴가": ctx["leave"]})
    h = ctx["history"]; st.caption(f"이 사용자: 걸린 거래 {h['flagged_tx']}건, 위반 확정 {h['violations']}건, 아님 처리 {h['cleared']}건")

with right:
    st.markdown("#### 결정")
    if not reviewer: st.warning("왼쪽에 검토자 이름을 입력하세요.")
    rule_opts = [e["rule_id"] for e in evs]
    rule_for = st.selectbox("대상 규칙", rule_opts, format_func=lambda r: f"{r[:3]} {s.RULE_NAME[r]}")
    decision = st.radio("판정", ["violation", "ok", "hold"], horizontal=True, format_func=lambda v: {"violation": "위반", "ok": "아님", "hold": "보류"}[v])
    reason = st.selectbox("사유", [c for c, _ in s.REASON_CODES], format_func=lambda c: dict(s.REASON_CODES)[c])
    memo = st.text_area("메모", height=80)
    if st.button("저장", type="primary", disabled=not reviewer, width='stretch'):
        s.create_review(tx_id, rule_for, decision, reason, memo, reviewer); s.log_event(reviewer, "review", {"tx_id": tx_id, "rule": rule_for, "decision": decision})
        st.success("저장됨"); st.rerun()
    st.markdown("##### 이 거래의 결정 이력")
    rv = s.get_reviews(tx_id)
    st.dataframe(rv, hide_index=True, width='stretch') if len(rv) else st.caption("없음")
