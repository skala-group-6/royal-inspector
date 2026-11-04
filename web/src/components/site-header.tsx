import type { ReactNode } from "react"
import { SidebarTrigger } from "@/components/ui/sidebar"

/** Top band on the provider background (same tone as the rail). Trigger toggles the section list panel. */
export function SiteHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center">
      <div className="flex w-full items-center gap-2 px-3">
        <SidebarTrigger className="-ml-1" />
        <h1 className="type-label">{title}</h1>
        <div className="ml-auto flex items-center gap-2">{right}</div>
      </div>
    </header>
  )
}
