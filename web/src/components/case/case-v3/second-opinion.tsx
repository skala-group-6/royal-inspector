import type { CaseBundle } from "@/types"

/** Layer 5: does the model lean the same way? Not a score — a side and two reasons, in small type at the bottom. */
export function SecondOpinion({ c }: { c: CaseBundle }) {
  const s = c.score
  if (!s || s.score_learned == null) return null
  const flagged = c.evidences.some((e) => e.severity === "violation")
  const high = s.score_learned >= 0.5
  const side = flagged ? (high ? "모델도 같은 쪽" : "모델은 다르게 봄") : high ? "모델은 평소와 다르다고 봄" : "모델도 특이점 없음"
  const why = s.top_features_learned.slice(0, 2).map((f) => f[2]).join(" · ")
  return <p data-slot="case-second-opinion" className="type-meta">{side}{why ? ` · ${why}` : ""} <span className="opacity-70">({s.learned_name ?? "모델"} · 시연용)</span></p>
}
