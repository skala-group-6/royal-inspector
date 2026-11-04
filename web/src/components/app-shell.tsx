import type { CSSProperties, ReactNode } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { SectionPanel } from "@/components/section-panel"
import { SiteHeader } from "@/components/site-header"
import { RAIL_WIDTH, useActiveSection } from "@/components/sections"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"

/**
 * Layout = shadcn "sidebar under a site header" pattern + `variant="inset"`:
 * the provider background (bg-sidebar) shows behind the header and the icon rail,
 * and SidebarInset is the rounded card that holds the section list panel and the main view.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const active = useActiveSection()
  return (
    <TooltipProvider>
      <SidebarProvider className="flex-col" style={{ "--sidebar-width": RAIL_WIDTH, "--header-height": "calc(var(--spacing) * 12)" } as CSSProperties}>
        <SiteHeader title={active?.title ?? "법인카드 점검"} />
        <div className="flex flex-1">
          <AppSidebar />
          <SidebarInset className="min-h-0 overflow-hidden">
            <div className="flex h-full min-h-0">
              {active?.List && <SectionPanel title={active.title} List={active.List} />}
              <main className="flex min-w-0 flex-1 flex-col overflow-auto">{children}</main>
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
      <Toaster />
    </TooltipProvider>
  )
}
