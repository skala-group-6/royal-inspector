import { Link, useParams } from "@tanstack/react-router"
import { Badge } from "@/components/ui/badge"
import { mock, mmdd, hhmm } from "@/mock"
import type { QueueRow } from "@/types"

/** Per-row badges: severity counts from the case bundle when available (mock), else n_rules; provenance for model/random; status when reviewed. */
function badges(r: QueueRow) {
  const ev = mock.cases[String(r.tx_id)]?.evidences ?? []
  const v = ev.length ? ev.filter((e) => e.severity === "violation").length : r.sev === 2 ? r.n_rules : 0
  const a = ev.length ? ev.length - v : r.sev === 2 ? 0 : r.n_rules
  const out: { label: string; variant: "destructive" | "outline" | "default" }[] = []
  if (v) out.push({ label: `위반 ${v}`, variant: "destructive" })
  if (a) out.push({ label: `참고 ${a}`, variant: "outline" })
  if (r.queue_source === "model") out.push({ label: "모델 추천", variant: "outline" })
  if (r.queue_source === "random") out.push({ label: "무작위 표본", variant: "outline" })
  if (r.review_status !== "unreviewed") out.push({ label: { violation: "위반 처리", ok: "아님 처리", hold: "보류" }[r.review_status], variant: "default" })
  return out
}

export function QueueList() {
  const { txId } = useParams({ strict: false }) as { txId?: string }
  const rows = mock.queue
  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between border-b px-4 py-2 text-xs text-muted-foreground">
        <span>{mock.period.period_from.slice(0, 7)} 큐 · {rows.length}건</span>
        <span>미검토 {rows.filter((r) => r.review_status === "unreviewed").length}</span>
      </div>
      {rows.map((r) => {
        const active = txId === String(r.tx_id)
        const done = r.review_status !== "unreviewed"
        return (
          <Link
            key={r.tx_id}
            to="/review/$txId"
            params={{ txId: String(r.tx_id) }}
            data-active={active || undefined}
            className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 border-b px-4 py-2.5 text-sm hover:bg-sidebar-accent data-active:bg-sidebar-accent data-active:shadow-[inset_3px_0_0_var(--sidebar-foreground)]"
          >
            <span className={`truncate font-medium ${done ? "text-muted-foreground" : ""}`}>{r.emp_name} · {r.dept}</span>
            <span className={`text-right font-medium tabular-nums ${done ? "text-muted-foreground" : ""}`}>{Math.round(r.total).toLocaleString("ko-KR")}</span>
            <span className="truncate text-xs text-muted-foreground">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)} · {r.merchant}</span>
            <span className="flex justify-end gap-1">
              {badges(r).map((b) => <Badge key={b.label} variant={b.variant} className="h-4 px-1.5 text-[10px]">{b.label}</Badge>)}
            </span>
          </Link>
        )
      })}
    </div>
  )
}
