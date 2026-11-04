import type { ComponentType } from "react"
import { SectionTitle } from "@/components/layout/list"
import { PANEL_WIDTH } from "@/components/sections"
import { usePanel } from "@/components/panel-state"

/** First column of the card: the active section's list on the panel surface. No dividers (docs/DESIGN.md).
 *  Visibility is the panel state (⌘B / header toggle), independent of the rail. */
export function SectionPanel({ title, List }: { title: string; List: ComponentType }) {
  const { open } = usePanel()
  if (!open) return null
  return (
    <aside className="flex shrink-0 flex-col overflow-hidden bg-surface-panel" style={{ width: PANEL_WIDTH }}>
      <SectionTitle>{title}</SectionTitle>
      <div className="min-h-0 flex-1 overflow-auto"><List /></div>
    </aside>
  )
}
