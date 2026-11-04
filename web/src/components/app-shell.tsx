import type { CSSProperties, ReactNode } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { SectionPanel } from "@/components/section-panel"
import { SiteHeader } from "@/components/site-header"
import { RAIL_WIDTH, useActiveSection } from "@/components/sections"
import { SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"

/** Layout knobs. Keep --sidebar-width-icon at shadcn's 3rem: it is coupled to the 32px menu buttons + 16px padding.
 *  The rail's visible width is set by its variant ("sidebar" = flush 48px) plus the card's left margin, not by shrinking the icon column. */
const SIZES = {
  "--header-height": "calc(var(--spacing) * 10)", // 40px
  "--sidebar-width": RAIL_WIDTH,                  // = --sidebar-width-icon (3rem): open and collapsed widths match
} as CSSProperties

/**
 * Provider background (bg-sidebar) shows behind the full-height icon rail and the header band.
 * The right column = header band + rounded card; the card holds the section list panel and the main view.
 * The right column is a plain flex column (not SidebarInset, whose inset styles would round the header band); the card is drawn here.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const active = useActiveSection()
  return (
    <TooltipProvider>
      <SidebarProvider style={SIZES} className="bg-surface-base">
        <AppSidebar />
        <div className="flex min-h-svh min-w-0 flex-1 flex-col">
          <SiteHeader title={active?.title ?? "법인카드 점검"} />
          <div className="mr-2 mb-2 ml-2 flex min-h-0 flex-1 overflow-hidden rounded-2xl bg-surface-card shadow-sm">
            {active?.List && <SectionPanel title={active.title} List={active.List} />}
            <main className="flex min-w-0 flex-1 flex-col overflow-auto">{children}</main>
          </div>
        </div>
      </SidebarProvider>
      <Toaster />
    </TooltipProvider>
  )
}
