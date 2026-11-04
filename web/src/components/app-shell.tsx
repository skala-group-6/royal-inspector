import type { CSSProperties, ReactNode } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { PANEL_WIDTH, RAIL_WIDTH, useActiveSection } from "@/components/sections"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"

export function AppShell({ children }: { children: ReactNode }) {
  const active = useActiveSection()
  // Outer sidebar width = rail + panel when the section has a list, rail only otherwise.
  const width = active?.List ? `calc(${RAIL_WIDTH} + ${PANEL_WIDTH})` : RAIL_WIDTH
  return (
    <TooltipProvider>
      <SidebarProvider style={{ "--sidebar-width": width, "--header-height": "calc(var(--spacing) * 12)" } as CSSProperties}>
        <AppSidebar />
        <SidebarInset>{children}</SidebarInset>
      </SidebarProvider>
      <Toaster />
    </TooltipProvider>
  )
}
