import type { Evidence } from "@/types"
import { won } from "@/lib/format"

/**
 * A rule hit is "observed value vs baseline". This maps each rule's evidence fields to those two cells so the findings table
 * reads as a comparison instead of a sentence. Rules without a mapping fall back to the headline/detail the service already writes.
 * Field names come from packs/corp_card/rules/sql and app/service.py evidence_text templates.
 */
export type Finding = { observed: string; baseline: string }
const s = (v: unknown, d = "—") => (v == null || v === "" ? d : String(v))
const n = (v: unknown) => (typeof v === "number" ? won(v) : s(v))

const MAP: Record<string, (ev: Record<string, unknown>) => Finding> = {
  R01: (e) => ({ observed: `${s(e.date)} (${s(e.weekday)}) 휴일 결제`, baseline: "휴일 사용은 사전 승인·소명 필요" }),
  R02: (e) => ({ observed: `${s(e.leave_type).trim()} ${s(e.leave_hours)}h 휴가일 ${s(e.time).slice(0, 5)}`, baseline: "휴가일엔 업무 지출 없음" }),
  R03: (e) => ({ observed: `${s(e.window_min)}분 안에 ${s(e.count_in_window)}건 · 합계 ${n(e.group_total)}`, baseline: `건당 한도 ${n(e.near_limit)}` }),
  R04: (e) => ({ observed: `${n(e.total)} 단위 금액 · 적요 "${s(e.memo, "")}"`, baseline: "선결제·단위 금액은 품의 필요" }),
  R05: (e) => ({ observed: `가맹점 ${s(e.merchant_sigungu)} = 주거지 ${s(e.home_sigungu)}`, baseline: `근무지 ${s(e.work_sigungu)}와 다름` }),
  R06: (e) => ({ observed: `${s(e.window_min)}분 안에 ${s(e.this_sigungu)} · ${s(e.other_sigungu)}`, baseline: "동일인이 두 지역에서 결제 불가" }),
  R07: (e) => ({ observed: `${s(e.trip_type)} 중 ${s(e.merchant_sido)} 결제`, baseline: `출장지 밖 (주거지 ${s(e.home_sido)} · 근무지 ${s(e.work_sido)})` }),
  R08: (e) => ({ observed: `업종 ${s(e.mcc)} · 계정 ${s(e.account)}`, baseline: "제한 업종 (Don'ts · 클린카드)" }),
  R09: (e) => ({ observed: `당일 ${s(e.same_day_count, "1")}회 · 14일 ${s(e.count_in_14d, "1")}회`, baseline: `하루 ${s(e.per_day)}회 · 14일 ${s(e.per_window)}회` }),
  R10: (e) => ({ observed: `${s(e.mcc)} ${n(e.total)} · 첨부 없음`, baseline: "증빙 필수 업종" }),
  R11: (e) => ({ observed: `업종 ${s(e.mcc)} · 계정 ${s(e.account)}`, baseline: e.reason === "overseas_trip_meal_not_trip_account" ? "해외출장 식사는 출장비 계정" : "금지 업종은 접대비 계정만" }),
  R12: (e) => ({ observed: `입문 ${s(e.badged_in_at)} → ${s(e.minutes_before_purchase)}분 뒤 ${s(e.merchant_sido)} 결제`, baseline: `근무지 ${s(e.work_sido)} · 반복 ${s(e.repeat_count)}회` }),
  R13: (e) => ({ observed: `의심 점수 ${s(e.score)}/4`, baseline: "적요 키워드·쇼핑 업종·심야/휴일·증빙" }),
  R14: (e) => ({ observed: `${s(e.trip_type)} 중 ${s(e.mcc)} ${n(e.total)}`, baseline: `계정 ${s(e.account)} (출장비 아님)` }),
  R15: (e) => ({ observed: `종료 ${s(e.days_before_end)}일 전 복귀 교통편`, baseline: "이후 출장지 소비 없음" }),
  R16: (e) => ({ observed: `${n(e.total)} (×${s(e.ratio)})`, baseline: `${s(e.peer_group)} 중앙값 ${n(e.peer_median)} · ${s(e.peer_n)}건` }),
  R17: (e) => ({ observed: `${s(e.merchant_sido)} 지역 ${s(e.mcc)}`, baseline: `자택방문교통비 · 주거지 ${s(e.home_sido)} · 근무지 ${s(e.work_sido)}` }),
  R18: (e) => ({ observed: `가맹점 = 승인자 주거지 ${s(e.approver_sigungu)}`, baseline: "승인자와 가맹점 지역 무관해야 함" }),
  R21: (e) => ({ observed: `${s(e.mcc)} ${n(e.total)} · 참석 ${s(e.attendees_in_memo, "?")}명`, baseline: "1인당 금액 기준" }),
}

export function finding(e: Evidence): Finding {
  const f = MAP[e.rule_id.slice(0, 3)]
  return f ? f(e.evidence) : { observed: e.headline, baseline: e.detail }
}
