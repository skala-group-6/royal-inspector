// Shapes mirror app/service.py outputs (see docs/API.md). Mock JSON and the future API client share these.
// tx ids are 64-bit integers in the DB; over JSON they are strings (JavaScript numbers lose precision past 2^53).
export type TxId = string
export type QueueSource = "rule" | "model" | "random"
export type Decision = "violation" | "ok" | "hold"
export type ReviewStatus = "unreviewed" | Decision

export interface QueueRow {
  queue_source: QueueSource; selection_prob: number; rank_in_source: number
  tx_id: TxId; tx_ts: string; emp_id: number; emp_name: string; dept: string; rank: string | null
  account_policy: string; merchant: string; mcc_name: string | null; total: number; is_synthetic: boolean
  rules: string[]; n_rules: number; sev: number; review_status: ReviewStatus
  score: number | null; score_learned: number | null
}
export interface Evidence {
  rule_id: string; rule_name: string; rule_class: string; severity: "violation" | "advisory"; cluster: string
  evidence: Record<string, unknown>; evidence_text: string; headline: string; detail: string; citation: string; explain: string
  related_tx: { tx_id: TxId; tx_ts: string; emp_name: string; account_policy: string; merchant: string; mcc_name: string; total: number }[]
  rule_version: number
}
export interface Peer { account_policy: string; mcc_name: string; n: number; median: number; p90: number; percentile_of_this: number; point_in_time?: boolean }
export interface Context {
  recent_tx: { tx_id: TxId; tx_ts: string; account_policy: string; merchant: string; mcc_name: string; merchant_addr: string | null; total: number; rules: string[] }[]
  peer: Peer | null; access_same_day: { access_ts: string; gate: string; event: string; direction: string | null }[]
  trip: { type: string; start: string; end: string } | null; leave: { type: string; hours: number } | null; holiday: boolean
  history: { flagged_tx: number; violations: number; cleared: number }
}
export interface TimelineRow { ts: string; kind: "카드" | "출입"; what: string; place: string | null; amount: number | null; focal: boolean }
export interface Precedent { precedent_id: string; kind: "case" | "review"; title: string; summary: string; cues: string[]; outcome: string | null; source: string; score: number; overlap: string[]; only_in_precedent: string[]; only_in_tx: string[] }
export interface Score { score: number; model_version: string; top_features: [string, number, string][]; score_learned: number | null; learned_name: string | null; top_features_learned: [string, number, string][]; disclaimer: string }
export interface Policy { account: string; description: string; dos: string; donts: string; required_evidence: string }
export interface Review { review_id: string; rule_id: string | null; decision: Decision; reason_code: string; memo: string; reviewer: string; created_at: string; superseded: boolean }
export interface Quantiles { n: number; p25: number | null; p50: number | null; p75: number | null; p90: number | null }
/** Point-in-time profile for the case charts (service.get_profile). */
export interface Profile {
  amount: { this: number; user: Quantiles; peer: Quantiles }
  weekly: { week_start: string; flagged: number; violations: number }[]
}
export interface CaseBundle {
  tx_id: TxId; transaction: Record<string, unknown> & { tx_ts: string; emp_name: string; dept: string; rank: string | null; merchant: string; mcc_name: string | null; total: number; account_policy: string; memo?: string | null; has_attachment: boolean }
  evidences: Evidence[]; context: Context; timeline: TimelineRow[]; precedents: { cases: Precedent[]; reviews: Precedent[]; summary: { n: number; violation: number; ok: number } }
  score: Score | null; policy: Policy | null; reviews: Review[]; profile: Profile
}
export interface MockData {
  period: { period_from: string; period_to: string }; queue: QueueRow[]; cases: Record<string, CaseBundle>
  rules: { rule_id: string; name: string; tier: "violation" | "advisory"; cluster: string; rule_class: string; explain: string; policy_ref: string }[]
  reason_codes: { code: string; label: string }[]
  summary: { source: QueueSource; n: number; reviewed: number; violation: number; ok: number; hold: number; hit_rate_pct: number | null; selection_prob: number; est_missed: number | null }[]
}
