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
st.caption("①규정: 걸리면 확인 대상 · ②임계치: 숫자 조정으로 건수 조절 · ③가설: 패턴 자체의 타당성 검증 필요")
view = sm[["rule_id", "name", "rule_class", "flagged", "reviewed", "violation", "ok", "hit_rate_pct"]].rename(
    columns={"rule_id": "규칙", "name": "이름", "rule_class": "부류", "flagged": "걸림", "reviewed": "검토", "violation": "위반", "ok": "아님", "hit_rate_pct": "적중률%"})
st.dataframe(view, width='stretch', hide_index=True)
st.info("왼쪽 메뉴의 **플래그 검토**에서 규칙을 골라 거래를 하나씩 판단하세요.")
