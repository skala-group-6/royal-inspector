import * as React from "react"
import { Link, useRouterState } from "@tanstack/react-router"
import { NavSecondary } from "@/components/nav-secondary"
import { NavUser } from "@/components/nav-user"
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import { HugeiconsIcon } from "@hugeicons/react"
import { CheckListIcon, ChartHistogramIcon, Layers01Icon, Settings05Icon, HelpCircleIcon, ShieldKeyIcon, PlayListIcon } from "@hugeicons/core-free-icons"

export const NAV = [
  { title: "검토", to: "/review", icon: CheckListIcon },
  { title: "요약", to: "/summary", icon: ChartHistogramIcon },
  { title: "큐·기간", to: "/queue", icon: PlayListIcon },
  { title: "규칙", to: "/rules", icon: Layers01Icon },
] as const

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const path = useRouterState({ select: (s) => s.location.pathname })
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="data-[slot=sidebar-menu-button]:p-1.5!">
              <Link to="/review">
                <HugeiconsIcon icon={ShieldKeyIcon} strokeWidth={2} className="size-5!" />
                <span className="text-base font-semibold">법인카드 점검</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton asChild isActive={path.startsWith(item.to)} tooltip={item.title}>
                    <Link to={item.to}>
                      <HugeiconsIcon icon={item.icon} strokeWidth={2} />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <NavSecondary items={[
          { title: "설정", url: "#", icon: <HugeiconsIcon icon={Settings05Icon} strokeWidth={2} /> },
          { title: "도움말", url: "#", icon: <HugeiconsIcon icon={HelpCircleIcon} strokeWidth={2} /> },
        ]} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={{ name: "감사자", email: "reviewer@company", avatar: "" }} />
      </SidebarFooter>
    </Sidebar>
  )
}
