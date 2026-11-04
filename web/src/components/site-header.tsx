import type { ReactNode } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { SidebarLeftIcon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { useSidebar } from "@/components/ui/sidebar"
import { usePanel } from "@/components/panel-state"

/** Same look as shadcn's SidebarTrigger, but toggles the list panel on desktop (the rail stays put); on mobile it opens the rail sheet. */
function PanelToggle() {
  const { toggle } = usePanel()
  const { isMobile, toggleSidebar } = useSidebar()
  return (
    <Button variant="ghost" size="icon-sm" className="-ml-1" onClick={isMobile ? toggleSidebar : toggle}>
      <HugeiconsIcon icon={SidebarLeftIcon} strokeWidth={2} />
      <span className="sr-only">목록 패널 열기/닫기</span>
    </Button>
  )
}

/** Top band on the provider background (same tone as the rail). */
export function SiteHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center">
      <div className="flex w-full items-center gap-2 px-3">
        <PanelToggle />
        <h1 className="type-label">{title}</h1>
        <div className="ml-auto flex items-center gap-2">{right}</div>
      </div>
    </header>
  )
}
