import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { mock } from "@/mock"

export function S02Shell() {
  return (
    <div className="bg-background h-[520px] overflow-hidden rounded-lg border">
      <div className="flex h-11 items-center justify-between border-b px-3 text-sm">
        <div className="flex items-center gap-3">
          <span className="font-medium">검토</span>
          <Badge variant="secondary">{mock.period.period_from} ~ {mock.period.period_to}</Badge>
          <span className="text-muted-foreground">큐 {mock.summary.reduce((a, s) => a + s.n, 0).toLocaleString()}건 · 오늘 처리 0건</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="text-muted-foreground gap-2">찾기 또는 질문… <Kbd>⌘K</Kbd></Button>
          <Button variant="ghost" size="sm"><Kbd>?</Kbd></Button>
        </div>
      </div>
      <ResizablePanelGroup orientation="horizontal" className="h-[calc(100%-2.75rem)]">
        <ResizablePanel defaultSize={42} minSize={28}>
          <div className="text-muted-foreground flex h-full items-center justify-center text-sm">좌: 큐 목록 (조각 03)</div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={58} minSize={35}>
          <div className="text-muted-foreground flex h-full items-center justify-center text-sm">우: 케이스 패널 (조각 04~06)</div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
