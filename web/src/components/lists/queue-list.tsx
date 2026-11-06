import { Link, useParams } from "@tanstack/react-router"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ListGroup, ListItem, ListMeta } from "@/components/layout/list"
import { QUEUE_PAGE, useCurrentPeriod, useQueue } from "@/api/queries"
import { mmdd, hhmm } from "@/lib/format"
import type { QueueRow } from "@/types"

/** Per-row badges: violation count when the row has a policy-backed rule (sev 2), otherwise advisory count; provenance for model/random; status when reviewed. */
function badges(r: QueueRow) {
  const v = r.sev === 2 ? r.n_rules : 0, a = r.sev === 2 ? 0 : r.n_rules
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
  const { period } = useCurrentPeriod()
  const { data: rows, isPending, error } = useQueue(period?.period_from, period?.period_to)
  if (error) return <ListMeta><span className="text-destructive">목록을 불러오지 못했습니다. API 서버가 켜져 있는지 확인하세요.</span></ListMeta>
  if (!period || isPending || !rows) return <div className="space-y-2 p-3">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
  return (
    <>
      <ListMeta>
        <span>{period.period_from.slice(0, 7)} 큐 · {period.n.toLocaleString("ko-KR")}건{period.n > rows.length ? ` 중 ${rows.length}` : ""}</span>
        <span>미검토 {rows.filter((r) => r.review_status === "unreviewed").length}{rows.length >= QUEUE_PAGE ? "+" : ""}</span>
      </ListMeta>
      <ListGroup>
        {rows.map((r) => {
          const done = r.review_status !== "unreviewed"
          return (
            <ListItem key={r.tx_id} asChild active={txId === r.tx_id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
              <Link to="/review/$txId" params={{ txId: r.tx_id }}>
                <span className={`truncate type-label ${done ? "text-muted-foreground" : ""}`}>{r.emp_name} · {r.dept}</span>
                <span className={`text-right type-value ${done ? "text-muted-foreground" : ""}`}>{Math.round(r.total).toLocaleString("ko-KR")}</span>
                <span className="truncate type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)} · {r.merchant}</span>
                <span className="flex justify-end gap-1">
                  {badges(r).map((b) => <Badge key={b.label} variant={b.variant} className="h-4 px-1.5 text-[10px]">{b.label}</Badge>)}
                </span>
              </Link>
            </ListItem>
          )
        })}
      </ListGroup>
    </>
  )
}
