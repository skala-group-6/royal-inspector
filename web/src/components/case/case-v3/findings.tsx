import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon, ArrowRight01Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { finding } from "@/lib/findings"
import type { CaseBundle, Finding } from "@/types"

/**
 * Layer 3: one line per finding, exactly as the server grouped them (service.get_findings: one per cluster, led by the strongest
 * rule, same-fact rules folded, other facts as chips). The screen knows no rule ids — only sentence, brief, severity, chips.
 * Opening a line pins observed | baseline | policy for every rule behind it.
 */
export function Findings({ c }: { c: CaseBundle }) {
  if (!c.findings?.length) return null
  return <ul data-slot="case-findings" className="flex flex-col gap-0.5">{c.findings.map((f) => <Line key={f.cluster} f={f} />)}</ul>
}

function Line({ f }: { f: Finding }) {
  const v = f.severity === "violation"
  return (
    <li>
      <Collapsible>
        <CollapsibleTrigger className="group grid w-full grid-cols-[1.25rem_1fr_auto_1rem] items-baseline gap-x-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover">
          <span className={`inline-flex items-center ${v ? "text-destructive" : "text-muted-foreground"}`} title={v ? "위반 가능" : "주의"}>
            <HugeiconsIcon icon={v ? Alert02Icon : InformationCircleIcon} strokeWidth={2} className="size-3.5" /><span className="sr-only">{v ? "위반 가능" : "주의"}</span>
          </span>
          <span className="flex min-w-0 items-baseline gap-1.5">
            <span className="truncate font-medium">{f.fact}</span>
            {f.chips.map((name) => <Badge key={name} variant="outline" className="h-4 shrink-0 px-1.5 text-[10px] font-normal">+ {name}</Badge>)}
          </span>
          <span className="truncate tabular-nums"><span>{f.brief_value}</span>{f.brief_verdict && <span className="text-muted-foreground"> · {f.brief_verdict}</span>}</span>
          <HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} className="size-3.5 self-center text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
        </CollapsibleTrigger>
        <CollapsibleContent className="flex flex-col gap-2 px-3 pb-2 pl-11">
          {f.evidences.map((e) => { const d = finding(e); return (
            <dl key={e.rule_id} className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-0.5 text-sm">
              {f.evidences.length > 1 && <><dt className="type-meta">규칙</dt><dd className="font-medium">{e.rule_name}</dd></>}
              <dt className="type-meta">관측값</dt><dd>{d.observed}</dd>
              <dt className="type-meta">기준</dt><dd className="text-muted-foreground">{d.baseline}</dd>
              {(e.citation || e.explain) && <><dt className="type-meta">규정</dt><dd className="type-meta">{e.citation || e.explain}</dd></>}
            </dl>
          ) })}
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}
