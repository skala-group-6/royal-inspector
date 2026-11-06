import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Label } from "@/components/ui/label"
import { documentsFor } from "@/pack/corp_card"
import type { CaseBundle } from "@/types"

/**
 * Layer 4: what to verify with. The policy sentence the top rule cites, the documents the reviewer must check outside the
 * system (checkboxes; we only know attachment yes/no), and past disciplinary cases. Checks are screen-only until stored.
 */
export function Basis({ c }: { c: CaseBundle }) {
  const cite = c.evidences.find((e) => e.citation)?.citation
  const docs = documentsFor(c.evidences.map((e) => e.rule_id))
  const [done, setDone] = useState<Record<string, boolean>>({})
  if (!cite && !docs.length && !c.precedents.cases.length) return null
  return (
    <div data-slot="case-basis" className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-2 text-sm">
      {cite && <><dt className="type-meta">규정</dt><dd className="truncate" title={cite}>{cite}</dd></>}
      {docs.length > 0 && (
        <>
          <dt className="type-meta">확인</dt>
          <dd className="flex flex-wrap gap-x-4 gap-y-1">
            {docs.map((d) => {
              const id = `doc-${d}`; const attached = d.startsWith("영수증") && c.transaction.has_attachment
              return (
                <span key={d} className="inline-flex items-center gap-1.5">
                  <Checkbox id={id} checked={!!done[d]} onCheckedChange={(v) => setDone((s) => ({ ...s, [d]: v === true }))} />
                  <Label htmlFor={id} className="font-normal">{d}{attached ? <span className="type-meta"> · 첨부 있음</span> : ""}</Label>
                </span>
              )
            })}
          </dd>
        </>
      )}
      {c.precedents.cases.length > 0 && (
        <>
          <dt className="type-meta">사례</dt>
          <dd>
            <Collapsible>
              <CollapsibleTrigger className="inline-flex items-center gap-1.5 rounded-md hover:bg-surface-hover">
                <span>과거 징계 사례</span><Badge variant="outline" className="h-4 px-1.5 text-[10px] tabular-nums">{c.precedents.cases.length}</Badge>
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-1.5">
                <ul className="flex flex-col gap-1">{c.precedents.cases.map((p) => <li key={p.precedent_id}><span className="font-medium">{p.title}</span> <span className="type-meta">{p.source}</span></li>)}</ul>
              </CollapsibleContent>
            </Collapsible>
          </dd>
        </>
      )}
    </div>
  )
}
