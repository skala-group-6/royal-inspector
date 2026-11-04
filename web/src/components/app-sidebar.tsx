import * as React from "react"
import { Link } from "@tanstack/react-router"
import { HugeiconsIcon } from "@hugeicons/react"
import { ShieldKeyIcon } from "@hugeicons/core-free-icons"
import { NavUser } from "@/components/nav-user"
import { SECTIONS, useActiveSection } from "@/components/sections"
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarHeader,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem,
} from "@/components/ui/sidebar"

/** Icon rail only: sections + user. `variant="sidebar"` = flush 48px; `collapsible="icon"` keeps open/closed widths equal. The list panel lives in the card (app-shell). */
export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const active = useActiveSection()
  return (
    <Sidebar variant="sidebar" collapsible="icon" className="border-r-0" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild className="md:h-8 md:p-0" tooltip={{ children: "법인카드 점검", hidden: false }}>
              <Link to="/review">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <HugeiconsIcon icon={ShieldKeyIcon} strokeWidth={2} className="size-4" />
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent className="px-1.5 md:px-0">
            <SidebarMenu>
              {SECTIONS.map((s) => (
                <SidebarMenuItem key={s.key}>
                  <SidebarMenuButton asChild isActive={active?.key === s.key} className="px-2.5 md:px-2" tooltip={{ children: s.title, hidden: false }}>
                    <Link to={s.to}>
                      <HugeiconsIcon icon={s.icon} strokeWidth={2} />
                      <span className="sr-only">{s.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={{ name: "감사자", email: "reviewer@company", avatar: "" }} />
      </SidebarFooter>
    </Sidebar>
  )
}
