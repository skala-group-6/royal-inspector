import { useEffect } from "react"
import { Outlet, useNavigate, useParams } from "@tanstack/react-router"
import { toast } from "sonner"
import { CasePanel } from "@/components/case/case-panel"
import { Skeleton } from "@/components/ui/skeleton"
import { logEvent, useCase, useCurrentPeriod, useQueue, useReview } from "@/api/queries"
import type { Decision } from "@/types"

export function ReviewLayout() {
  return <Outlet />
}

export function ReviewEmpty() {
  return <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">왼쪽 목록에서 건을 선택하세요.</div>
}

const LABEL: Record<Decision, string> = { violation: "위반", ok: "아님", hold: "보류" }
const typing = (e: KeyboardEvent) => ["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName) || (e.target as HTMLElement)?.isContentEditable

/** The case panel on live data. A verdict is saved through POST /tx/{id}/review, then the case and the list refresh. J/K move along the queue. */
export function ReviewCase() {
  const { txId } = useParams({ from: "/review/$txId" })
  const navigate = useNavigate()
  const { period } = useCurrentPeriod()
  const queue = useQueue(period?.period_from, period?.period_to)
  const { data: c, isPending, error } = useCase(txId)
  const review = useReview(txId)
  const row = queue.data?.find((r) => r.tx_id === txId)

  useEffect(() => { logEvent("open_case", { tx_id: txId }) }, [txId])
  useEffect(() => {
    const rows = queue.data; if (!rows) return
    const onKey = (e: KeyboardEvent) => {
      if (typing(e) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key !== "j" && e.key !== "k") return
      const i = rows.findIndex((r) => r.tx_id === txId); if (i < 0) return
      const next = rows[e.key === "j" ? i + 1 : i - 1]; if (next) navigate({ to: "/review/$txId", params: { txId: next.tx_id } })
    }
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey)
  }, [queue.data, txId, navigate])

  if (error) return <div className="p-6 text-sm text-muted-foreground">해당 건을 불러오지 못했습니다. (ID {txId}) {String(error.message)}</div>
  if (isPending || !c) return <div className="space-y-3 p-8"><Skeleton className="h-6 w-1/2" /><Skeleton className="h-24" /><Skeleton className="h-40" /></div>
  return (
    <CasePanel
      c={c}
      source={row?.queue_source}
      period={period?.period_from.slice(0, 7)}
      saving={review.isPending}
      onVerdict={(d, reason, memo) =>
        review.mutate({ decision: d, reason_code: reason, memo }, {
          onSuccess: () => toast(`판정 저장: ${LABEL[d]}${reason ? ` · ${reason}` : ""}`, { description: "이전 판정은 이력으로 남습니다." }),
          onError: (err) => toast.error("저장 실패", { description: err.message }),
        })}
    />
  )
}
