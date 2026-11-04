import { Outlet, useParams } from "@tanstack/react-router"
import { toast } from "sonner"
import { CasePanel } from "@/components/case/case-panel"
import { mock } from "@/mock"

export function ReviewLayout() {
  return <Outlet />
}

export function ReviewEmpty() {
  return <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">왼쪽 목록에서 건을 선택하세요.</div>
}

/** The case panel (proposal under review in /gallery scenarios). Verdicts are not persisted until the API lands (plan 3). */
export function ReviewCase() {
  const { txId } = useParams({ from: "/review/$txId" })
  const c = mock.cases[txId]
  if (!c) return <div className="p-6 text-sm text-muted-foreground">해당 건이 없습니다. (ID {txId})</div>
  const source = mock.queue.find((r) => r.tx_id === txId)?.queue_source
  return (
    <CasePanel
      c={c}
      source={source}
      onVerdict={(d, reason, memo) => toast(`판정 ${({ violation: "위반", ok: "아님", hold: "보류" })[d]}${reason ? ` · ${reason}` : ""}${memo ? ` · ${memo}` : ""}`, { description: "저장은 API 연결(계획 3) 뒤에 동작합니다." })}
    />
  )
}
