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

/**
 * shadcn block "sidebar-09" (collapsible nested sidebars): one outer Sidebar holding
 * a fixed icon rail (sections) and a wider panel (the active section's list).
 * Collapsing the outer sidebar leaves only the rail.
 */
export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const active = useActiveSection()
  const List = active?.List
  return (
    <Sidebar collapsible="icon" className="overflow-hidden *:data-[sidebar=sidebar]:flex-row" {...props}>
      {/* Rail */}
      <Sidebar collapsible="none" className="w-[calc(var(--sidebar-width-icon)+1px)]! border-r">
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
                        <span>{s.title}</span>
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

      {/* Panel: the active section's list. Absent for sections without one (e.g. 요약). */}
      {List && (
        <Sidebar collapsible="none" className="hidden flex-1 md:flex">
          <SidebarHeader className="h-(--header-height) justify-center border-b px-4">
            <div className="text-base font-medium">{active?.title}</div>
          </SidebarHeader>
          <SidebarContent>
            <List />
          </SidebarContent>
        </Sidebar>
      )}
    </Sidebar>
  )
}
