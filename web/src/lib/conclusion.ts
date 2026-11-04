import type { CaseBundle, QueueSource } from "@/types"

/**
 * One short line under the property grid. It names what kind of case this is; it does NOT repeat amount, merchant or time,
 * which the grid already shows once. Composed from rule outputs only. The server will own this later (roadmap step 6).
 */
const LEADS = ["R02", "R01", "R05", "R07", "R12", "R17", "R18", "R08", "R11", "R03", "R06", "R10", "R15", "R14", "R09", "R16", "R13", "R04", "R21"]
const s = (v: unknown) => (v == null ? "" : String(v))

export function conclusion(c: CaseBundle, source?: QueueSource): string {
  if (!c.evidences.length) {
    return source === "model" ? "걸린 규칙 없음 · 모델이 평소와 다르다고 본 건" : source === "random" ? "걸린 규칙 없음 · 무작위 표본 (대부분 '아님'이 정상)" : "걸린 규칙 없음"
  }
  const vio = c.evidences.filter((e) => e.severity === "violation")
  const pool = vio.length ? vio : c.evidences
  const lead = [...pool].sort((a, b) => LEADS.indexOf(a.rule_id.slice(0, 3)) - LEADS.indexOf(b.rule_id.slice(0, 3)))[0]
  const ev = lead.evidence
  const T: Record<string, () => string> = {
    R02: () => `${s(ev.leave_type).trim() || "휴가"} 등록일 사용`,
    R01: () => "휴일 사용",
    R05: () => `주거지 인근(${s(ev.merchant_sigungu)}) 사용, 근무지와 다른 지역`,
    R07: () => `${s(ev.trip_type) || "출장"} 중 출장지 밖(${s(ev.merchant_sido)}) 사용`,
    R12: () => "사옥 입문 직후 타지역 결제 — 카드 대여 의심",
    R17: () => "자택방문교통비를 다른 지역에서 사용",
    R18: () => `승인자 주거지 인근(${s(ev.approver_sigungu)}) 가맹점`,
    R08: () => "제한 업종 사용",
    R11: () => "업종과 계정 불일치",
    R03: () => `${s(ev.window_min)}분 안에 ${s(ev.count_in_window)}건 분할 결제`,
    R06: () => "같은 시각 두 지역 결제",
    R10: () => "증빙 필수 업종인데 첨부 없음",
    R15: () => "출장 종료 전 조기 복귀 교통편",
    R14: () => "출장 중 식사를 출장비 외 계정으로",
    R09: () => "주유 빈도 과다",
    R16: () => `동료 중앙값의 ${s(ev.ratio)}배 금액`,
    R13: () => "개인 물품 구매 의심",
    R04: () => "단위 금액 선결제 의심",
    R21: () => "참석 인원 대비 과다 금액",
  }
  const head = (T[lead.rule_id.slice(0, 3)] ?? (() => lead.headline))()
  const others = vio.filter((e) => e !== lead).map((e) => e.rule_name)
  return others.length ? `${head} · 그 밖에 ${others.slice(0, 2).join(", ")}${others.length > 2 ? ` 외 ${others.length - 2}` : ""}` : head
}
