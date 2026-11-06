import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon, ArrowRight01Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { finding } from "@/lib/findings"
import { briefFor, claimFor } from "@/pack/corp_card"
import type { CaseBundle, Evidence } from "@/types"

/**
 * Layer 3: one line per rule in one grammar — severity icon · plain sentence · `관측값 · 판단어` · chevron.
 * Opening a line pins the full observed | baseline pair and the policy citation below it (click, not hover: keyboard users
 * and side-by-side comparison both need it to stay).
 */
export function Findings({ c }: { c: CaseBundle }) {
  if (!c.evidences.length) return null
  const rows = [...c.evidences].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "violation" ? -1 : 1))
  return <ul data-slot="case-findings" className="flex flex-col gap-0.5">{rows.map((e) => <Line key={e.rule_id} e={e} c={c} />)}</ul>
}

function Line({ e, c }: { e: Evidence; c: CaseBundle }) {
  const f = finding(e); const b = briefFor(e); const v = e.severity === "violation"
  return (
    <li>
      <Collapsible>
        <CollapsibleTrigger className="group grid w-full grid-cols-[1.25rem_1fr_auto_1rem] items-baseline gap-x-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover">
          <span className={`inline-flex items-center ${v ? "text-destructive" : "text-muted-foreground"}`} title={v ? "위반 가능" : "주의"}>
            <HugeiconsIcon icon={v ? Alert02Icon : InformationCircleIcon} strokeWidth={2} className="size-3.5" /><span className="sr-only">{v ? "위반 가능" : "주의"}</span>
          </span>
          <span className="truncate font-medium">{claimFor(e, c)}</span>
          <span className="truncate tabular-nums"><span>{b.value}</span>{b.verdict && <span className="text-muted-foreground"> · {b.verdict}</span>}</span>
          <HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} className="size-3.5 self-center text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
        </CollapsibleTrigger>
        <CollapsibleContent className="px-3 pb-2 pl-11">
          <dl className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-0.5 text-sm">
            <dt className="type-meta">관측값</dt><dd>{f.observed}</dd>
            <dt className="type-meta">기준</dt><dd className="text-muted-foreground">{f.baseline}</dd>
            {(e.citation || e.explain) && <><dt className="type-meta">규정</dt><dd className="type-meta">{e.citation || e.explain}</dd></>}
          </dl>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}
