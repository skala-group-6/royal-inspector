import type { ReactNode } from "react"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

/** Top band on the provider background (same tone as the rail). Trigger toggles the section list panel. */
export function SiteHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center">
      <div className="flex w-full items-center gap-1 px-3 lg:gap-2">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
        <h1 className="text-sm font-medium">{title}</h1>
        <div className="ml-auto flex items-center gap-2">{right}</div>
      </div>
    </header>
  )
}
