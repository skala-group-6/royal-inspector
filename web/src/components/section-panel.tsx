import type { ComponentType } from "react"
import { SectionTitle } from "@/components/layout/list"
import { PANEL_WIDTH } from "@/components/sections"
import { useSidebar } from "@/components/ui/sidebar"

/** First column of the card: the active section's list on the panel surface. No dividers (docs/DESIGN.md).
 *  Visibility reuses the sidebar `open` state (⌘B / trigger). */
export function SectionPanel({ title, List }: { title: string; List: ComponentType }) {
  const { open } = useSidebar()
  if (!open) return null
  return (
    <aside className="flex shrink-0 flex-col overflow-hidden bg-surface-panel" style={{ width: PANEL_WIDTH }}>
      <SectionTitle>{title}</SectionTitle>
      <div className="min-h-0 flex-1 overflow-auto"><List /></div>
    </aside>
  )
}
