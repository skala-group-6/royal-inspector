import type { ComponentType } from "react"
import { useRouterState } from "@tanstack/react-router"
import { CheckListIcon, Database01Icon, Layers01Icon, ChartHistogramIcon } from "@hugeicons/core-free-icons"
import { QueueList } from "@/components/lists/queue-list"
import { RuleList } from "@/components/lists/rule-list"
import { DataRuns } from "@/components/lists/data-runs"

/** App sections = rail items. `List` is what the secondary sidebar shows for that section; sections without one show the rail only. */
export type Section = {
  key: "review" | "data" | "rules" | "summary"
  title: string
  to: "/review" | "/data" | "/rules" | "/summary"
  icon: typeof CheckListIcon
  List?: ComponentType
}

export const SECTIONS: readonly Section[] = [
  { key: "review", title: "검토", to: "/review", icon: CheckListIcon, List: QueueList },
  { key: "data", title: "데이터", to: "/data", icon: Database01Icon, List: DataRuns },
  { key: "rules", title: "규칙", to: "/rules", icon: Layers01Icon, List: RuleList },
  { key: "summary", title: "요약", to: "/summary", icon: ChartHistogramIcon },
]

/** Active section is derived from the URL, never stored. */
export function useActiveSection(): Section | undefined {
  const path = useRouterState({ select: (s) => s.location.pathname })
  return SECTIONS.find((s) => path === s.to || path.startsWith(s.to + "/"))
}

export const PANEL_WIDTH = "20rem"
// Inset-variant rail: icon width + container padding (p-2 each side) + 2px, same as the collapsed width, so toggling never moves the card.
export const RAIL_WIDTH = "calc(var(--sidebar-width-icon) + var(--spacing) * 4 + 2px)"
