import { Badge } from "@/components/ui/badge"
import { humanLine, violationFindings } from "@/pack/corp_card"
import { won, hhmm, mmdd } from "@/lib/format"
import type { CaseBundle, QueueSource } from "@/types"

/** Layer 1: one plain sentence (strongest rule + one supporting clause), the amount, who/when/where, count of policy-backed situations (clusters). Never a verdict. */
export function Conclusion({ c, source }: { c: CaseBundle; source?: QueueSource }) {
  const t = c.transaction
  const { head, tail } = humanLine(c, source)
  const vio = violationFindings(c)
  return (
    <div data-slot="case-conclusion" className="flex items-start justify-between gap-6">
      <div className="min-w-0">
        <h2 className="text-xl font-semibold leading-snug">{head}{tail ? <span className="text-muted-foreground">. {tail}</span> : ""}</h2>
        <p className="mt-1.5 truncate type-meta">{t.emp_name} · {t.dept}{t.rank ? ` · ${t.rank}` : ""} · {mmdd(t.tx_ts)} {hhmm(t.tx_ts)}{t.weekday ? ` (${String(t.weekday)})` : ""} · {t.merchant}</p>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-2xl font-semibold tabular-nums">{won(t.total)}</div>
        {vio > 0 && <Badge variant="destructive" className="mt-1">위반 {vio}</Badge>}
      </div>
    </div>
  )
}
