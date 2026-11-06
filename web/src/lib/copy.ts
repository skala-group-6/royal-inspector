import type { CaseBundle, QueueSource } from "@/types"

/**
 * The first thing a reviewer reads: one plain-Korean sentence saying what kind of case this is, in the words a colleague would use.
 * No system vocabulary, no numbers (the amount sits beside it). Composed from the strongest rule + one supporting clause.
 */
const ORDER = ["R02", "R01", "R05", "R07", "R12", "R17", "R18", "R08", "R11", "R03", "R06", "R10", "R15", "R14", "R09", "R16", "R13", "R04", "R21"]
const s = (v: unknown) => (v == null ? "" : String(v))
const MCC_WORD: Record<string, string> = { 일반주점: "술집", 주점: "술집", 유흥주점: "유흥주점", 단란주점: "단란주점", 노래방: "노래방", 골프장: "골프장", 골프연습장: "골프연습장", 일반음식점: "식당", 커피전문점: "카페", 주유소: "주유소", 인터넷상거래: "온라인 쇼핑", 오픈마켓: "온라인 쇼핑", 편의점: "편의점" }
const place = (c: CaseBundle) => MCC_WORD[s(c.transaction.mcc_name)] ?? (s(c.transaction.mcc_name) || "가맹점")

const HEAD: Record<string, (c: CaseBundle, ev: Record<string, unknown>) => string> = {
  R02: (c, ev) => `${s(ev.leave_type).trim() || "휴가"} 낸 날 ${place(c)} 결제`,
  R01: (c) => `휴일에 ${place(c)} 결제`,
  R05: (c) => `집 근처 ${place(c)} 결제`,
  R07: (c, ev) => `${s(ev.trip_type) || "출장"} 중인데 출장지 밖에서 ${place(c)} 결제`,
  R12: () => "회사에 들어온 직후 다른 지역에서 결제",
  R17: () => "자택방문 교통비를 다른 지역에서 사용",
  R18: (c) => `승인자 집 근처 ${place(c)} 결제`,
  R08: (c) => `${place(c)} 결제 (제한 업종)`,
  R11: (c) => `${place(c)} 결제를 맞지 않는 계정으로 처리`,
  R03: (_c, ev) => `같은 가게에서 ${s(ev.window_min)}분 안에 ${s(ev.count_in_window)}번 나눠 결제`,
  R06: () => "같은 시각에 두 지역에서 결제",
  R10: (c) => `${place(c)} 결제인데 증빙 없음`,
  R15: () => "출장 끝나기 전에 미리 돌아오는 표 구매",
  R14: (c) => `출장 중 ${place(c)} 결제를 출장비 아닌 계정으로`,
  R09: () => "주유가 너무 잦음",
  R16: (c, ev) => `동료들보다 ${s(ev.ratio)}배 비싼 ${place(c)} 결제`,
  R13: () => "개인 물건을 산 것으로 보임",
  R04: (c) => `${place(c)}에 딱 떨어지는 금액 (선결제 의심)`,
  R21: () => "참석 인원에 비해 큰 식사 금액",
}
const TAIL: Record<string, (ev: Record<string, unknown>) => string> = {
  R18: () => "승인자 집도 같은 동네",
  R08: () => "제한 업종",
  R11: () => "계정도 맞지 않음",
  R02: (ev) => `${s(ev.leave_type).trim() || "휴가"} 낸 날`,
  R01: () => "휴일",
  R10: () => "증빙 없음",
  R16: (ev) => `동료보다 ${s(ev.ratio)}배`,
  R03: () => "나눠 결제",
  R06: () => "같은 시각 다른 지역",
  R14: () => "출장비 아닌 계정",
  R05: () => "집 근처",
}

export function humanLine(c: CaseBundle, source?: QueueSource): { head: string; tail?: string } {
  if (!c.evidences.length) {
    if (source === "model") return { head: "규칙엔 안 걸렸지만 평소와 다름", tail: "모델 추천" }
    if (source === "random") return { head: "걸린 규칙 없음", tail: "무작위 표본 · 대부분 '아님'이 정상" }
    return { head: "걸린 규칙 없음" }
  }
  const vio = c.evidences.filter((e) => e.severity === "violation"); const pool = vio.length ? vio : c.evidences
  const sorted = [...pool].sort((a, b) => ORDER.indexOf(a.rule_id.slice(0, 3)) - ORDER.indexOf(b.rule_id.slice(0, 3)))
  const lead = sorted[0]; const k = lead.rule_id.slice(0, 3)
  const head = (HEAD[k] ?? (() => lead.headline))(c, lead.evidence)
  const second = sorted.slice(1).find((e) => TAIL[e.rule_id.slice(0, 3)])
  const tail = second ? TAIL[second.rule_id.slice(0, 3)](second.evidence) : undefined
  return { head, tail }
}
