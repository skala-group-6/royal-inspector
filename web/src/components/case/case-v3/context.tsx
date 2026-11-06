import { lazy, Suspense } from "react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowRight01Icon } from "@hugeicons/core-free-icons"
import { contextFor, strongestRule } from "@/pack/corp_card"
import { won } from "@/lib/format"
import type { CaseBundle, QueueSource } from "@/types"

const AmountBars = lazy(() => import("@/components/charts/amount-bars").then((m) => ({ default: m.AmountBars })))
const AmountDots = lazy(() => import("@/components/charts/amount-dots").then((m) => ({ default: m.AmountDots })))
const DayTimeline = lazy(() => import("@/components/charts/day-timeline").then((m) => ({ default: m.DayTimeline })))
const Fallback = <div className="h-16 animate-pulse rounded-lg bg-surface-panel" />

/** Layer 2: one fixed slot; the strongest rule decides what fills it. Unflagged rows (model/random) get the amount comparison. Nothing to show → nothing rendered. */
export function Context({ c, source }: { c: CaseBundle; source?: QueueSource }) {
  const lead = strongestRule(c)
  const kind = lead ? contextFor(lead.rule_id) : source ? "amount" : "none"
  if (kind === "none") return null
  if (kind === "day") {
    if (!c.timeline.length) return null
    return (
      <div data-slot="case-context" className="rounded-lg bg-surface-panel px-4 py-3">
        <p className="mb-2 text-sm font-medium">그날 동선</p>
        <Suspense fallback={Fallback}><DayTimeline c={c} /></Suspense>
      </div>
    )
  }
  const { user, peer } = c.profile.amount; const x = c.transaction.total
  if (user.n < 5 && peer.n < 5) return null
  const ratio = user.p50 ? x / user.p50 : null
  const pct = c.context.peer?.percentile_of_this
  const parts = [ratio != null ? `이 사람 평소의 ${ratio >= 10 ? Math.round(ratio) : ratio.toFixed(1)}배` : null, pct != null ? `동료 100명 중 ${Math.max(1, Math.round(100 - pct))}등` : null].filter(Boolean)
  return (
    <div data-slot="case-context" className="rounded-lg bg-surface-panel px-4 py-3">
      <p className="text-sm font-medium">{parts.length ? `${parts.join(", ")} 금액` : `금액 비교 · 본인 평소 ${won(user.p50 ?? 0)}`}</p>
      <Suspense fallback={Fallback}><AmountBars profile={c.profile} className="mt-2" /></Suspense>
      {c.context.recent_tx.length >= 3 && (
        <Collapsible>
          <CollapsibleTrigger className="group mt-1 flex items-center gap-1 rounded-md px-1 py-1 type-meta hover:bg-surface-hover">
            <HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} className="size-3 transition-transform group-data-[state=open]:rotate-90" />본인 최근 거래 {c.context.recent_tx.length}건
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-1"><Suspense fallback={Fallback}><AmountDots c={c} /></Suspense></CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
