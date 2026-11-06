import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon, ArrowRight01Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { finding } from "@/lib/findings"
import { briefFor, claimFor, groupByCluster } from "@/pack/corp_card"
import type { CaseBundle, Evidence } from "@/types"

/**
 * Layer 3: one line per *cluster* (rules that fire on the same situation share a catalog cluster; the label builder counts a
 * cluster once, so does the screen). The line is the cluster's strongest rule — icon · plain sentence · `관측값 · 판단어` —
 * with the other rules of the cluster as small chips. Opening a line pins observed | baseline | policy for every rule in it.
 */
export function Findings({ c }: { c: CaseBundle }) {
  if (!c.evidences.length) return null
  return <ul data-slot="case-findings" className="flex flex-col gap-0.5">{groupByCluster(c.evidences).map((g) => <Line key={g.lead.rule_id} lead={g.lead} others={g.others} c={c} />)}</ul>
}

function Line({ lead, others, c }: { lead: Evidence; others: Evidence[]; c: CaseBundle }) {
  const b = briefFor(lead); const v = lead.severity === "violation"
  return (
    <li>
      <Collapsible>
        <CollapsibleTrigger className="group grid w-full grid-cols-[1.25rem_1fr_auto_1rem] items-baseline gap-x-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover">
          <span className={`inline-flex items-center ${v ? "text-destructive" : "text-muted-foreground"}`} title={v ? "위반 가능" : "주의"}>
            <HugeiconsIcon icon={v ? Alert02Icon : InformationCircleIcon} strokeWidth={2} className="size-3.5" /><span className="sr-only">{v ? "위반 가능" : "주의"}</span>
          </span>
          <span className="flex min-w-0 items-baseline gap-1.5">
            <span className="truncate font-medium">{claimFor(lead, c)}</span>
            {others.map((o) => <Badge key={o.rule_id} variant="outline" className="h-4 shrink-0 px-1.5 text-[10px] font-normal">+ {o.rule_name}</Badge>)}
          </span>
          <span className="truncate tabular-nums"><span>{b.value}</span>{b.verdict && <span className="text-muted-foreground"> · {b.verdict}</span>}</span>
          <HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} className="size-3.5 self-center text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
        </CollapsibleTrigger>
        <CollapsibleContent className="flex flex-col gap-2 px-3 pb-2 pl-11">
          {[lead, ...others].map((e) => { const f = finding(e); return (
            <dl key={e.rule_id} className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-0.5 text-sm">
              {others.length > 0 && <><dt className="type-meta">규칙</dt><dd className="font-medium">{e.rule_name}</dd></>}
              <dt className="type-meta">관측값</dt><dd>{f.observed}</dd>
              <dt className="type-meta">기준</dt><dd className="text-muted-foreground">{f.baseline}</dd>
              {(e.citation || e.explain) && <><dt className="type-meta">규정</dt><dd className="type-meta">{e.citation || e.explain}</dd></>}
            </dl>
          ) })}
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}
