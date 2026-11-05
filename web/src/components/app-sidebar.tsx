import * as React from "react"
import { Link } from "@tanstack/react-router"
import { HugeiconsIcon } from "@hugeicons/react"
import { Moon02Icon, ShieldKeyIcon, Sun03Icon } from "@hugeicons/core-free-icons"
import { NavUser } from "@/components/nav-user"
import { SECTIONS, useActiveSection } from "@/components/sections"
import { useTheme } from "@/components/theme-provider"
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarHeader,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem,
} from "@/components/ui/sidebar"

/** Dark ↔ light, same as the D key. Icon and tooltip follow the applied theme via the dark: variant, so they stay right in "system" mode when the OS flips. */
function ThemeToggle() {
  const { toggleTheme } = useTheme()
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          onClick={toggleTheme}
          className="px-2.5 md:px-2"
          tooltip={{
            children: (
              <>
                <span className="dark:hidden">다크 모드로 전환 (D)</span>
                <span className="hidden dark:inline">라이트 모드로 전환 (D)</span>
              </>
            ),
          }}
        >
          <HugeiconsIcon icon={Sun03Icon} strokeWidth={2} className="dark:hidden" />
          <HugeiconsIcon icon={Moon02Icon} strokeWidth={2} className="hidden dark:block" />
          <span className="sr-only">테마 전환</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

/** Icon rail only: sections + theme toggle + user. Pinned collapsed by the provider (open={false}), so it is always the 48px icon rail and tooltips show by default. The list panel lives in the card (app-shell). */
export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const active = useActiveSection()
  return (
    <Sidebar variant="sidebar" collapsible="icon" className="group-data-[side=left]:border-r-0" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild className="md:h-8 md:p-0" tooltip="법인카드 점검">
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
                  <SidebarMenuButton asChild isActive={active?.key === s.key} className="px-2.5 md:px-2" tooltip={s.title}>
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
        <ThemeToggle />
        <NavUser user={{ name: "감사자", email: "reviewer@company", avatar: "" }} />
      </SidebarFooter>
    </Sidebar>
  )
}
