import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { useIsMobile } from "@/hooks/use-mobile"

/**
 * List-panel visibility. Deliberately separate from shadcn's sidebar open/collapsed state:
 * the rail is pinned to the collapsed (icon) state, so toggling the panel never re-lays-out the rail buttons.
 * Persists to localStorage; ⌘B / Ctrl+B toggles on desktop (on mobile shadcn's own ⌘B opens the rail sheet).
 */
const KEY = "panel_open"
type PanelState = { open: boolean; toggle: () => void }
const Ctx = createContext<PanelState | null>(null)

export function PanelProvider({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(() => localStorage.getItem(KEY) !== "false")
  const toggle = useCallback(() => {
    setOpen((v) => {
      localStorage.setItem(KEY, String(!v))
      return !v
    })
  }, [])

  useEffect(() => {
    if (isMobile) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "b" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); toggle() }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [isMobile, toggle])

  const value = useMemo(() => ({ open, toggle }), [open, toggle])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function usePanel(): PanelState {
  const v = useContext(Ctx)
  if (!v) throw new Error("usePanel must be used inside PanelProvider")
  return v
}
