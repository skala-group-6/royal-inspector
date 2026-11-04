import type { CSSProperties, ReactNode } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { SectionPanel } from "@/components/section-panel"
import { SiteHeader } from "@/components/site-header"
import { RAIL_WIDTH, useActiveSection } from "@/components/sections"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"

/** Layout knobs. Rail width follows --sidebar-width-icon (+ inset padding); header height is --header-height. */
const SIZES = {
  "--sidebar-width-icon": "3rem",          // rail icon column (48px). Rail total = this + 1rem padding + 2px
  "--header-height": "calc(var(--spacing) * 12)", // 48px
  "--sidebar-width": RAIL_WIDTH,
} as CSSProperties

/**
 * `variant="inset"`: the provider background (bg-sidebar) shows behind the full-height icon rail and the header band.
 * The right column = header band + rounded card; the card holds the section list panel and the main view.
 * SidebarInset is kept as the right column (peer coupling with the rail) but made transparent; the card is the inner div.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const active = useActiveSection()
  return (
    <TooltipProvider>
      <SidebarProvider style={SIZES}>
        <AppSidebar />
        <SidebarInset className="m-0! min-h-0 rounded-none bg-transparent shadow-none md:m-0!">
          <SiteHeader title={active?.title ?? "법인카드 점검"} />
          <div className="mr-2 mb-2 flex min-h-0 flex-1 overflow-hidden rounded-2xl bg-background shadow-sm">
            {active?.List && <SectionPanel title={active.title} List={active.List} />}
            <main className="flex min-w-0 flex-1 flex-col overflow-auto">{children}</main>
          </div>
        </SidebarInset>
      </SidebarProvider>
      <Toaster />
    </TooltipProvider>
  )
}
