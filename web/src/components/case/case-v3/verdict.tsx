import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Decision } from "@/types"

/**
 * Verdict bar: three buttons, nothing else. The current verdict is the pressed button. "아님" saves at once; "위반"/"보류"
 * open an inline reason + memo (Enter saves, Esc cancels). Keys V/N/H when not typing. Saving is the caller's job (onVerdict).
 */
export function Verdict({ current, reasonCodes = [], saving, onVerdict }: { current?: Decision; reasonCodes?: { code: string; label: string }[]; saving?: boolean; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const [pending, setPending] = useState<Decision | null>(null)
  const [reason, setReason] = useState(""); const [memo, setMemo] = useState("")
  const pick = (d: Decision) => { if (d === "ok") { onVerdict?.(d); return } setPending(d); setReason(""); setMemo("") }
  const save = () => { if (pending) onVerdict?.(pending, reason || undefined, memo || undefined); setPending(null) }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || e.metaKey || e.ctrlKey || e.altKey || pending) return
      if (e.key === "v") pick("violation"); else if (e.key === "n") pick("ok"); else if (e.key === "h") pick("hold")
    }
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey)
  })
  const label: Record<Decision, string> = { violation: "위반", ok: "아님", hold: "보류" }
  return (
    <div data-slot="case-verdict" className="flex shrink-0 items-center gap-2 bg-surface-panel px-8 py-3">
      {pending ? (
        <>
          <span className={`type-label ${pending === "violation" ? "text-destructive" : ""}`}>{label[pending]}</span>
          <Select value={reason} onValueChange={setReason}>
            <SelectTrigger className="w-52" size="sm"><SelectValue placeholder={pending === "violation" ? "조치" : "사유"} /></SelectTrigger>
            <SelectContent>{reasonCodes.map((r) => <SelectItem key={r.code} value={r.code}>{r.label}</SelectItem>)}</SelectContent>
          </Select>
          <Input autoFocus value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="메모 (선택)" className="h-8 flex-1" onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setPending(null) }} />
          <Button size="sm" variant={pending === "violation" ? "destructive" : "default"} onClick={save}>저장 <Kbd>↵</Kbd></Button>
          <Button size="sm" variant="ghost" onClick={() => setPending(null)}>취소 <Kbd>Esc</Kbd></Button>
        </>
      ) : (
        <>
          <Button variant={current === "violation" ? "destructive" : "outline"} className={current === "violation" ? "" : "text-destructive"} disabled={saving} onClick={() => pick("violation")}>위반 <Kbd>V</Kbd></Button>
          <Button variant={current === "ok" ? "default" : "outline"} disabled={saving} onClick={() => pick("ok")}>아님 <Kbd>N</Kbd></Button>
          <Button variant={current === "hold" ? "default" : "outline"} disabled={saving} onClick={() => pick("hold")}>보류 <Kbd>H</Kbd></Button>
        </>
      )}
    </div>
  )
}
