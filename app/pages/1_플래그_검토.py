import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import streamlit as st, pandas as pd
from app import service as s

st.set_page_config(page_title="플래그 검토", layout="wide")
st.markdown("""<style>
 .block-container{padding-top:1.2rem;padding-bottom:1rem} h1{font-size:1.4rem!important;margin-bottom:.2rem}
 h3{font-size:1.05rem!important;margin:.4rem 0 .2rem} p,li{font-size:.92rem;margin-bottom:.2rem}
 div[data-testid="stMetric"]{padding:0} .small{font-size:.85rem;color:#666}
</style>""", unsafe_allow_html=True)
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
F = dict(rule_ids=sel_rules or None, min_total=min_total or None, sort=sort, synthetic_only=syn)

df = s.list_flags(review_status=status, page=page, page_size=page_size, **F)
st.title("플래그 검토")
st.caption(f"{len(df)}건 (페이지 {page}) · 한 줄의 **맨 왼쪽 체크박스**를 누르면 아래에 상세가 열립니다.")
show = df.assign(규칙=df.rules.map(lambda l: " ".join(r[:3] for r in l)), 금액=df.total.map(lambda v: f"{v:,.0f}"),
                 일시=df.tx_ts.dt.strftime("%m-%d %H:%M"), 합성=df.is_synthetic.map({True: "T", False: ""}))[
    ["tx_id", "일시", "emp_name", "dept", "rank", "account_policy", "merchant", "mcc_name", "금액", "규칙", "review_status", "합성"]].rename(
    columns={"emp_name": "사용자", "dept": "부서", "rank": "직급", "account_policy": "계정", "merchant": "가맹점", "mcc_name": "업종", "review_status": "상태"})
ev = st.dataframe(show, width='stretch', hide_index=True, on_select="rerun", selection_mode="single-row", height=300, key="flags_table")
sel = ev.selection.rows if ev and ev.selection else []
if sel:
    picked = int(df.tx_id.iloc[sel[0]])
    if picked != st.session_state.get("tx_id"):
        st.session_state["tx_id"] = picked; s.log_event(reviewer, "open_case", {"tx_id": picked})
tx_id = st.session_state.get("tx_id")
if tx_id is None:
    st.info("위 표에서 한 줄의 맨 왼쪽 체크박스를 클릭하면 여기에 상세가 열립니다."); st.stop()
t = s.get_transaction(tx_id); evs = s.get_evidence(tx_id); ctx = s.get_context(tx_id)

# ---------- case: one screen, three questions ----------
st.divider()
st.markdown(f"### #{tx_id} · {t['tx_ts']:%m-%d(%a) %H:%M} · {t['emp_name']} ({t['dept']} {t['rank']}) · **{t['merchant']}** [{t['mcc_name']}] · **{t['total']:,.0f}원** · 계정 {t['account_policy']}")
flags_line = " · ".join(f"휴일" if ctx["holiday"] else "" for _ in [0]) 
badges = [b for b in ["휴일" if ctx["holiday"] else None, f"휴가 {ctx['leave']['type']} {ctx['leave']['hours']}h" if ctx["leave"] else None,
          f"{ctx['trip']['type']} {ctx['trip']['start']}~{ctx['trip']['end']}" if ctx["trip"] else None, f"적요: {t['memo']}" if t.get("memo") else None,
          f"증빙 {'있음' if t['has_attachment'] else '없음'}"] if b]
p = ctx["peer"]
if p: badges.append(f"동료 비교: {p['account_policy']}×{p['mcc_name']} 중앙값 {p['median']:,.0f}원, 이 건은 상위 {100-p['percentile_of_this']:.0f}%")
h = ctx["history"]; badges.append(f"이 사용자 이력: 걸림 {h['flagged_tx']} · 위반 {h['violations']} · 아님 {h['cleared']}")
st.markdown('<p class="small">' + " &nbsp;|&nbsp; ".join(badges) + "</p>", unsafe_allow_html=True)

left, right = st.columns([3, 1.4])
with left:
    st.markdown("**① 왜 걸렸나**")
    sev_icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}
    rt = pd.DataFrame([{"": sev_icon.get(e["severity"], ""), "규칙": f"{e['rule_id'][:3]} {e['rule_name']}", "부류": e["rule_class"][:1], "근거": e["evidence_text"]} for e in evs])
    st.dataframe(rt, hide_index=True, width='stretch', height=min(40 + 36 * len(rt), 260), column_config={"근거": st.column_config.TextColumn(width="large"), "": st.column_config.TextColumn(width="small"), "부류": st.column_config.TextColumn(width="small")})
    rel = pd.concat([e["related_tx"].assign(규칙=e["rule_id"][:3]) for e in evs if len(e["related_tx"])], ignore_index=True) if any(len(e["related_tx"]) for e in evs) else None
    if rel is not None:
        st.markdown("**관련 거래** (분할·동시간 등 함께 봐야 할 건)")
        st.dataframe(rel.drop_duplicates("tx_id"), hide_index=True, width='stretch', height=min(40 + 36 * len(rel), 180))

    st.markdown("**② 그날 이 사람의 동선** (출입 + 카드, 시간순 · ★ = 이 거래)")
    tl = s.get_day_timeline(tx_id)
    tl_show = tl.assign(시각=tl.ts.dt.strftime("%H:%M"), 구분=tl.kind, 내용=tl.what, 장소=tl.place, 금액=tl.amount.map(lambda v: f"{v:,.0f}" if pd.notna(v) else ""), 규칙=tl.rules.fillna(""), _=tl.focal.map({True: "★", False: ""}))[["_", "시각", "구분", "내용", "장소", "금액", "규칙"]]
    st.dataframe(tl_show, hide_index=True, width='stretch', height=min(40 + 36 * len(tl_show), 300))

    pol = s.get_policy(t["account_policy"])
    with st.expander(f"③ 규정 발췌 — {t['account_policy']}", expanded=True):
        if pol:
            c1, c2 = st.columns(2)
            c1.markdown("**허용(Do's)**\n\n" + pol["dos"].replace("\n", "  \n")); c2.markdown("**금지(Don'ts)**\n\n" + pol["donts"].replace("\n", "  \n"))
            if pol["required_evidence"]: st.caption("필수 증빙: " + pol["required_evidence"].replace("\n", " / "))
        else: st.caption("규정표에 없는 계정")
    with st.expander("같은 사람 최근 거래 20건 / 원본 근거 JSON"):
        r = ctx["recent_tx"]; st.dataframe(r.assign(규칙=r.rules.map(lambda l: " ".join(x[:3] for x in l))).drop(columns=["rules"]), hide_index=True, width='stretch')
        for e in evs: st.json({e["rule_id"]: e["evidence"]}, expanded=False)

with right:
    st.markdown("**판정**")
    if not reviewer: st.warning("왼쪽에 검토자 이름을 입력하세요.")
    rule_opts = [e["rule_id"] for e in evs]
    rule_for = st.selectbox("대상 규칙", rule_opts, format_func=lambda r: f"{r[:3]} {s.RULE_NAME[r]}", label_visibility="collapsed")
    decision = st.radio("판정", ["violation", "ok", "hold"], horizontal=True, format_func=lambda v: {"violation": "위반", "ok": "아님", "hold": "보류"}[v], label_visibility="collapsed")
    reason = st.selectbox("사유", [c for c, _ in s.REASON_CODES], format_func=lambda c: dict(s.REASON_CODES)[c])
    memo = st.text_input("메모")
    auto_next = st.checkbox("저장 후 다음 미검토 건으로", value=True)
    if st.button("저장", type="primary", disabled=not reviewer, width='stretch'):
        s.create_review(tx_id, rule_for, decision, reason, memo, reviewer); s.log_event(reviewer, "review", {"tx_id": tx_id, "rule": rule_for, "decision": decision})
        if auto_next:
            nxt = s.next_unreviewed(tx_id, **F)
            if nxt: st.session_state["tx_id"] = int(nxt)
        st.rerun()
    rv = s.get_reviews(tx_id)
    st.markdown("**이 거래의 결정 이력**")
    if len(rv): st.dataframe(rv[["rule_id", "decision", "reason_code", "reviewer", "created_at", "superseded"]], hide_index=True, width='stretch', height=min(40 + 36 * len(rv), 200))
    else: st.caption("없음")
