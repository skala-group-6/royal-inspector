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
const ORDER = ["R02", "R01", "R05", "R07", "R12", "R17", "R18", "R08", "R11", "R03", "R06", "R10", "R15", "R14", "R09", "R16", "R13", "R04", "R21"]
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
  const vio = c.evidences.filter((e) => e.severity === "violation"); const pool = vio.length ? vio : c.evidences
  const sorted = [...pool].sort((a, b) => ORDER.indexOf(a.rule_id.slice(0, 3)) - ORDER.indexOf(b.rule_id.slice(0, 3)))
  const lead = sorted[0]; const k = lead.rule_id.slice(0, 3)
  const head = (HEAD[k] ?? (() => lead.headline))(c, lead.evidence)
  const second = sorted.slice(1).find((e) => TAIL[e.rule_id.slice(0, 3)])
  const tail = second ? TAIL[second.rule_id.slice(0, 3)](second.evidence) : undefined
  return { head, tail }
}

/** The rule the screen leads with: policy-backed first, then the pack's order of strength. */
export function strongestRule(c: CaseBundle): Evidence | undefined {
  if (!c.evidences.length) return undefined
  const vio = c.evidences.filter((e) => e.severity === "violation"); const pool = vio.length ? vio : c.evidences
  return [...pool].sort((a, b) => ORDER.indexOf(a.rule_id.slice(0, 3)) - ORDER.indexOf(b.rule_id.slice(0, 3)))[0]
}

/** Layer 3 row title: one plain sentence per finding (same templates as the conclusion). */
export function claimFor(e: Evidence, c: CaseBundle): string {
  return (HEAD[e.rule_id.slice(0, 3)] ?? (() => e.headline))(c, e.evidence)
}

/**
 * Layer 3 row brief — one grammar for every rule: `관측값 · 판단어`. The value is the number when there is one, else the place /
 * category / account; the verdict word is one of five (같음 · 금지 · 아님 · 초과 · 없음, plus 휴일/휴가일/동시/출장 중 for time rules).
 * Details (baseline numbers, place names of the baseline) belong to the expanded row, not here.
 */
export type Brief = { value: string; verdict: string }
const sg = (v: unknown) => s(v).replace(/^(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\s+/, "")
const BRIEF: Record<string, (ev: Record<string, unknown>) => Brief> = {
  R01: (ev) => ({ value: `${s(ev.date).slice(5)} (${s(ev.weekday)})`, verdict: "휴일" }),
  R02: (ev) => ({ value: `${s(ev.leave_type).trim() || "휴가"} ${s(ev.leave_hours)}h`, verdict: "휴가일" }),
  R03: (ev) => ({ value: `${s(ev.window_min)}분 안 ${s(ev.count_in_window)}건`, verdict: "분할" }),
  R04: (ev) => ({ value: `${Number(ev.total).toLocaleString("ko-KR")}원`, verdict: "단위 금액" }),
  R05: (ev) => ({ value: sg(ev.merchant_sigungu), verdict: "집과 같음" }),
  R06: (ev) => ({ value: `${s(ev.window_min)}분 안 2곳`, verdict: "동시" }),
  R07: (ev) => ({ value: s(ev.merchant_sido), verdict: "출장지 밖" }),
  R08: (ev) => ({ value: s(ev.mcc), verdict: "금지 업종" }),
  R09: (ev) => ({ value: `당일 ${s(ev.same_day_count, "1")}회 · 14일 ${s(ev.count_in_14d, "1")}회`, verdict: "초과" }),
  R10: (ev) => ({ value: s(ev.mcc), verdict: "증빙 없음" }),
  R11: (ev) => ({ value: s(ev.account), verdict: ev.reason === "overseas_trip_meal_not_trip_account" ? "출장비 아님" : "접대비 아님" }),
  R12: (ev) => ({ value: `입문 ${s(ev.minutes_before_purchase)}분 뒤 ${s(ev.merchant_sido)}`, verdict: `${s(ev.repeat_count)}회 반복` }),
  R13: (ev) => ({ value: `신호 ${s(ev.score)}/4`, verdict: "개인 물품 의심" }),
  R14: (ev) => ({ value: s(ev.account), verdict: "출장비 아님" }),
  R15: (ev) => ({ value: `종료 ${s(ev.days_before_end)}일 전`, verdict: "조기 복귀" }),
  R16: (ev) => ({ value: `${s(ev.ratio)}배`, verdict: "동료 초과" }),
  R17: (ev) => ({ value: s(ev.merchant_sido), verdict: "경로 밖" }),
  R18: (ev) => ({ value: sg(ev.approver_sigungu), verdict: "승인자 집과 같음" }),
  R21: (ev) => ({ value: `참석 ${s(ev.attendees_in_memo) || "?"}명`, verdict: "금액 초과" }),
}
export function briefFor(e: Evidence): Brief {
  const f = BRIEF[e.rule_id.slice(0, 3)]
  return f ? f(e.evidence) : { value: e.detail, verdict: "" }
}

/** Rules that fired on the same situation (catalog cluster), ordered by strength; the lead is the strongest rule of each cluster. */
export function groupByCluster(evs: Evidence[]): { cluster: string; lead: Evidence; others: Evidence[] }[] {
  const rank = (e: Evidence) => (e.severity === "violation" ? 0 : 100) + Math.max(0, ORDER.indexOf(e.rule_id.slice(0, 3)))
  const by = new Map<string, Evidence[]>()
  for (const e of [...evs].sort((a, b) => rank(a) - rank(b))) { const k = e.cluster ?? e.rule_id; by.set(k, [...(by.get(k) ?? []), e]) }
  return [...by.entries()].map(([cluster, list]) => ({ cluster, lead: list[0], others: list.slice(1) }))
}
/** Same count for a list row, which only carries rule ids: needs the rule catalog (GET /rules) for tier and cluster. */
export type RuleInfo = { rule_id: string; tier: "violation" | "advisory"; cluster: string }
export function violationClustersOf(ruleIds: string[], rules: RuleInfo[]): number {
  const by = new Map(rules.map((r) => [r.rule_id, r]))
  return new Set(ruleIds.map((id) => by.get(id)).filter((r) => r?.tier === "violation").map((r) => r!.cluster)).size
}
/** How many policy-backed situations (clusters with a violation-tier rule) this case has — the number the "위반 n" badge shows. */
export const violationClusters = (evs: Evidence[]) => new Set(evs.filter((e) => e.severity === "violation").map((e) => e.cluster ?? e.rule_id)).size
