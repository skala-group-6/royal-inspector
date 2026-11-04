import { mock } from "@/mock"
import type { CaseBundle, TxId } from "@/types"

/** Named scenarios for design review: /gallery/case/$slug → the real review screen on a case that exercises that shape. */
export const SCENARIOS: { slug: string; title: string; pick: (c: CaseBundle) => boolean }[] = [
  { slug: "multi-violation", title: "위반 여러 개", pick: (c) => c.evidences.filter((e) => e.severity === "violation").length >= 4 },
  { slug: "single-violation", title: "위반 하나, 소액", pick: (c) => c.evidences.length === 1 && c.evidences[0].severity === "violation" },
  { slug: "advisory-only", title: "참고만 있음", pick: (c) => c.evidences.length > 0 && c.evidences.every((e) => e.severity === "advisory") },
  { slug: "model-pick", title: "걸린 규칙 없음 · 모델 추천", pick: (c) => !c.evidences.length && source(c.tx_id) === "model" },
  { slug: "random-sample", title: "걸린 규칙 없음 · 무작위 표본", pick: (c) => !c.evidences.length && source(c.tx_id) === "random" },
  { slug: "reviewed", title: "이미 판정된 건", pick: (c) => c.reviews.length > 0 },
  { slug: "with-related", title: "함께 볼 거래 있음", pick: (c) => c.evidences.some((e) => e.related_tx.length > 0) },
]

function source(txId: TxId) { return mock.queue.find((r) => r.tx_id === txId)?.queue_source }

export function scenarioTx(slug: string): TxId | undefined {
  const s = SCENARIOS.find((x) => x.slug === slug); if (!s) return undefined
  return (Object.values(mock.cases) as CaseBundle[]).find(s.pick)?.tx_id
}
