import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app import service as s

st.set_page_config(page_title="법인카드 점검 (임시 검토 화면)", layout="wide")
st.title("법인카드 점검 — 요약")
st.caption("임시 검토 화면. 숫자는 현재 임계치 기준이며, 적중률은 검토 결정이 쌓일수록 의미가 생깁니다.")

c1, c2, c3 = st.columns(3)
date_from = c1.date_input("시작일", value=None); date_to = c2.date_input("종료일", value=None)
scope = c3.selectbox("대상", ["all", "leaders"], format_func=lambda v: {"all": "전 구성원", "leaders": "리더(팀장 이상)"}[v])
sm = s.get_summary(date_from, date_to, scope)

m1, m2, m3, m4 = st.columns(4)
m1.metric("걸린 플래그", int(sm.flagged.sum())); m2.metric("검토 완료", int(sm.reviewed.sum()))
m3.metric("위반 확정", int(sm.violation.sum())); m4.metric("전체 적중률", f"{(100*sm.violation.sum()/max(sm.reviewed.sum(),1)):.1f}%")

st.subheader("규칙별 현황")
st.caption("위반 가능 🔴: 규정에 근거가 있어 걸리면 확인 대상 · 참고 ⚪: 통계·가설 기반, 우선순위 참고용. 임계치와 등급은 팩 규칙 카탈로그(packs/corp_card/rules/catalog.yaml) v2")
view = sm[["rule_id", "name", "rule_class", "flagged", "reviewed", "violation", "ok", "hit_rate_pct"]].rename(
    columns={"rule_id": "규칙", "name": "이름", "rule_class": "부류", "flagged": "걸림", "reviewed": "검토", "violation": "위반", "ok": "아님", "hit_rate_pct": "적중률%"})
st.dataframe(view, width='stretch', hide_index=True)
periods = s.list_queue_periods()
if len(periods):
    st.subheader("검토 큐 출처별 현황")
    labels_p = [f"{r.period_from}~{r.period_to}" for r in periods.itertuples()]
    i = st.selectbox("큐 기간", range(len(labels_p)), format_func=lambda k: labels_p[k])
    qs = s.get_queue_summary(str(periods.period_from.iloc[i]), str(periods.period_to.iloc[i]))
    st.dataframe(qs.rename(columns={"source": "출처", "n": "건수", "reviewed": "검토", "violation": "위반", "ok": "아님", "hold": "보류", "hit_rate_pct": "적중률%", "selection_prob": "선택확률", "est_missed": "추정 놓침(건)"}), hide_index=True, width='stretch')
    rnd = qs[qs.source == "random"]
    if len(rnd) and rnd.reviewed.iloc[0]:
        r = rnd.iloc[0]; st.caption(f"🎲 무작위 {int(r.reviewed)}건 검토 중 위반 {int(r.violation)}건 → 규칙에 안 걸린 거래의 위반율 추정 {100*r.violation/r.reviewed:.1f}% (≈ {int(r.est_missed or 0):,}건). 규칙이 놓치는 것의 첫 측정이며, 위반 건은 새 규칙 발굴의 입력입니다.")
    else: st.caption("🎲 무작위 표본의 판정이 쌓이면 '규칙이 놓치는 비율'이 여기에 표시됩니다.")
st.info("왼쪽 메뉴의 **플래그 검토**에서 거래를 하나씩 판단하세요.")
