import { useNavigate, useParams } from "@tanstack/react-router"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft01Icon, ArrowRight01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SCENARIOS, scenarioTx } from "@/lib/scenarios"

/** Design-review aid in the header: shows when the selected case is one of the named scenarios; dropdown + prev/next move between them. */
export function ScenarioSwitcher() {
  const { txId } = useParams({ strict: false }) as { txId?: string }
  const navigate = useNavigate()
  const items = SCENARIOS.map((s) => ({ ...s, tx: scenarioTx(s.slug) })).filter((s) => s.tx)
  const idx = items.findIndex((s) => s.tx === txId)
  if (idx < 0) return null
  const go = (i: number) => navigate({ to: "/gallery/case/$slug", params: { slug: items[(i + items.length) % items.length].slug } })
  return (
    <div className="flex items-center gap-1">
      <span className="type-meta mr-1">시나리오</span>
      <Button variant="ghost" size="icon-sm" onClick={() => go(idx - 1)} aria-label="이전 시나리오"><HugeiconsIcon icon={ArrowLeft01Icon} strokeWidth={2} /></Button>
      <Select value={items[idx].slug} onValueChange={(slug) => navigate({ to: "/gallery/case/$slug", params: { slug } })}>
        <SelectTrigger size="sm" className="h-7 w-56"><SelectValue /></SelectTrigger>
        <SelectContent>{items.map((s, i) => <SelectItem key={s.slug} value={s.slug}>{i + 1}. {s.title}</SelectItem>)}</SelectContent>
      </Select>
      <Button variant="ghost" size="icon-sm" onClick={() => go(idx + 1)} aria-label="다음 시나리오"><HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} /></Button>
      <span className="type-meta ml-1 tabular-nums">{idx + 1}/{items.length}</span>
    </div>
  )
}
