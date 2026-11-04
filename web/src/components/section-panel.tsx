import type { ComponentType } from "react"
import { PANEL_WIDTH } from "@/components/sections"
import { useSidebar } from "@/components/ui/sidebar"

/** First column of the inset card: the active section's list. Visibility reuses the sidebar `open` state (⌘B / trigger). */
export function SectionPanel({ title, List }: { title: string; List: ComponentType }) {
  const { open } = useSidebar()
  if (!open) return null
  return (
    <aside className="flex shrink-0 flex-col overflow-hidden border-r" style={{ width: PANEL_WIDTH }}>
      <div className="flex h-(--header-height) shrink-0 items-center border-b px-4 text-base font-medium">{title}</div>
      <div className="min-h-0 flex-1 overflow-auto"><List /></div>
    </aside>
  )
}
