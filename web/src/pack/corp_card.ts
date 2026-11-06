import type { CaseBundle, Evidence, QueueSource } from "@/types"

/**
 * Corporate-card pack: everything the review screen needs to know about this domain's rules, in three tables.
 * The screen (components/case/case-v3) owns the five layers and their order; this file owns what goes into them
 * (docs/PACK_SPEC.md §7). Moves into the rule catalog (`context`, `documents`) later.
 */

/** Layer 2: which context the strongest rule needs. place/time rules → that day's timeline; amount rules → amount comparison; else none. */
export type ContextKind = "day" | "amount" | "none"
const CONTEXT: Record<string, ContextKind> = {
  R01: "day", R02: "day", R05: "day", R06: "day", R07: "day", R12: "day", R15: "day", R17: "day", R18: "day",
  R03: "amount", R04: "amount", R16: "amount", R21: "amount",
  R08: "none", R09: "none", R10: "none", R11: "none", R13: "none", R14: "none",
}
export const contextFor = (ruleId: string): ContextKind => CONTEXT[ruleId.slice(0, 3)] ?? "none"

/** Layer 4: documents the reviewer must check outside the system for each rule (we only know attachment yes/no). */
const DOCUMENTS: Record<string, string[]> = {
  R01: ["사전 승인·품의서", "출장/근무 기록"], R02: ["휴가 결재 원문"], R03: ["영수증(분할 건 전부)", "사전 품의서"], R04: ["영수증", "사전 품의서"],
  R05: ["영수증", "업무 관련성 소명"], R06: ["영수증 2건", "참석자 명단"], R07: ["출장 결재 원문", "영수증"], R08: ["사전 품의서", "참석자 명단"],
  R09: ["차량 운행 일지"], R10: ["영수증 원본"], R11: ["사전 품의서"], R12: ["카드 소지자 확인"], R13: ["영수증·구매 내역"], R14: ["출장 결재 원문"],
  R15: ["출장 결재 원문", "교통편 영수증"], R16: ["영수증", "참석자 명단"], R17: ["자택방문 신청서"], R18: ["참석자 명단", "사전 품의서"], R21: ["영수증", "참석자 명단"],
}
export const documentsFor = (ruleIds: string[]): string[] => [...new Set(ruleIds.flatMap((r) => DOCUMENTS[r.slice(0, 3)] ?? []))]

/**
 * Layer 1: the first thing a reviewer reads: one plain-Korean sentence saying what kind of case this is, in the words a colleague would use.
 * No system vocabulary, no numbers (the amount sits beside it). Composed from the strongest rule + one supporting clause.
 */
const s = (v: unknown, d = "") => (v == null || v === "" ? d : String(v))
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
  const leads = (c.findings ?? []).map((f) => f.evidences[0]); if (!leads.length) return { head: c.evidences[0].fact }
  const lead = leads[0]; const k = lead.rule_id.slice(0, 3)
  const head = (HEAD[k] ?? (() => lead.fact))(c, lead.evidence)
  const second = leads.slice(1).find((e) => TAIL[e.rule_id.slice(0, 3)])
  const tail = second ? TAIL[second.rule_id.slice(0, 3)](second.evidence) : undefined
  return { head, tail }
}

/** The rule the screen leads with: policy-backed first, then the pack's order of strength. */
export function strongestRule(c: CaseBundle): Evidence | undefined {
  if (!c.evidences.length) return undefined
  const vio = c.evidences.filter((e) => e.severity === "violation"); const pool = vio.length ? vio : c.evidences
  return [...pool].sort((a, b) => ORDER.indexOf(a.rule_id.slice(0, 3)) - ORDER.indexOf(b.rule_id.slice(0, 3)))[0]
}

/** Policy-backed situations = findings with a violation-tier lead (server-grouped). The "위반 n" badge. */
export const violationFindings = (c: CaseBundle) => (c.findings ?? []).filter((f) => f.severity === "violation").length
/** The rule the screen leads with: the lead of the first finding (server order: violation first, then the catalog's order). */
export function strongestRule(c: CaseBundle): Evidence | undefined { return c.findings?.[0]?.evidences[0] }
