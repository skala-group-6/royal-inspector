import { mock } from "@/mock"

/** Load/queue history for the 데이터 section. One period in mock; real list comes with the API. */
export function DataRuns() {
  const p = mock.period
  return (
    <div className="flex flex-col">
      <div className="border-b px-4 py-2 text-xs text-muted-foreground">적재·큐 이력</div>
      <div className="border-b bg-sidebar-accent px-4 py-2.5 text-sm shadow-[inset_3px_0_0_var(--sidebar-foreground)]">
        <div className="font-medium">{p.period_from} ~ {p.period_to}</div>
        <div className="text-xs text-muted-foreground">큐 {mock.queue.length}건 · 규칙 {mock.rules.length}개</div>
      </div>
    </div>
  )
}
