import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { finding } from "@/lib/findings"
import type { CaseBundle, Evidence } from "@/types"

/** Layer 3: one line per rule — severity icon, rule name, observed | baseline. Opening a line shows the rule's policy citation. */
export function Findings({ c }: { c: CaseBundle }) {
  if (!c.evidences.length) return null
  const rows = [...c.evidences].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "violation" ? -1 : 1))
  return <ul data-slot="case-findings" className="flex flex-col gap-0.5">{rows.map((e) => <Line key={e.rule_id} e={e} />)}</ul>
}

function Line({ e }: { e: Evidence }) {
  const f = finding(e); const v = e.severity === "violation"
  return (
    <li>
      <Collapsible>
        <CollapsibleTrigger className="grid w-full grid-cols-[1.25rem_9rem_1fr_1fr] items-baseline gap-x-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover">
          <span className={`inline-flex items-center ${v ? "text-destructive" : "text-muted-foreground"}`} title={v ? "위반 가능" : "주의"}>
            <HugeiconsIcon icon={v ? Alert02Icon : InformationCircleIcon} strokeWidth={2} className="size-3.5" /><span className="sr-only">{v ? "위반 가능" : "주의"}</span>
          </span>
          <span className="truncate font-medium">{e.rule_name}</span>
          <span className="truncate">{f.observed}</span>
          <span className="truncate text-muted-foreground">{f.baseline}</span>
        </CollapsibleTrigger>
        <CollapsibleContent className="px-3 pb-2 pl-[13.5rem] type-meta">{e.citation || e.explain}</CollapsibleContent>
      </Collapsible>
    </li>
  )
}
