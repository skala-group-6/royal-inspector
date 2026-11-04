import { useState, type ReactNode } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { conclusion } from "@/lib/conclusion"
import { mock, won, hhmm, mmdd } from "@/mock"
import type { CaseBundle, Decision, QueueSource } from "@/types"

/**
 * Review case panel (wireframe v2 + docs/DESIGN.md): conclusion first, reasons as a list, rare information collapsed,
 * verdict bar at the bottom. No lines: grouping by surface tone and spacing only.
 */
export function CasePanel({ c, source, onVerdict }: { c: CaseBundle; source?: QueueSource; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const t = c.transaction
  const ts = `${t.tx_ts.slice(0, 10)} ${hhmm(t.tx_ts)}`
  const related = c.evidences.flatMap((e) => e.related_tx)
  const lastReview = c.reviews[0]
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-8 pt-7 pb-6">
        <div className="type-meta">{t.emp_name} · {t.dept}{t.rank ? ` · ${t.rank}` : ""} · 전표 {String(t.sap_doc_no ?? "")}</div>
        <div className="mt-0.5 type-label">{won(t.total)} · {t.merchant} · {ts} · {t.account_policy}</div>

        <h2 className="mt-6 text-xl font-semibold leading-snug tracking-tight">{conclusion(c, source)}</h2>

        {c.evidences.length > 0 && (
          <ul className="mt-5 flex flex-col gap-1.5">
            {c.evidences.map((e) => (
              <li key={e.rule_id} className="grid grid-cols-[2.5rem_1fr] gap-x-3 rounded-lg bg-surface-panel px-3 py-2">
                <span className={`pt-px text-xs font-semibold ${e.severity === "violation" ? "text-destructive" : "text-muted-foreground"}`}>{e.severity === "violation" ? "위반" : "참고"}</span>
                <span>
                  <span className="text-sm">{e.headline}</span>
                  <span className="type-meta"> · {e.detail}</span>
                  <div className="mt-0.5 type-meta">{e.citation}</div>
                </span>
              </li>
            ))}
          </ul>
        )}
        {!c.evidences.length && c.context.peer && (
          <p className="mt-5 text-sm text-muted-foreground">같은 계정·업종 동료 중앙값 {won(c.context.peer.median)} · 이 건은 상위 {Math.round(100 - c.context.peer.percentile_of_this)}%.</p>
        )}

        <div className="mt-6 flex flex-col">
          <More title={`그날의 흐름 · ${c.timeline.length}건`}>
            <ol className="flex flex-col gap-1">
              {c.timeline.map((x, i) => (
                <li key={i} className={`grid grid-cols-[3rem_3rem_1fr_auto] gap-x-3 text-sm ${x.focal ? "font-semibold" : "text-muted-foreground"}`}>
                  <span className="tabular-nums">{hhmm(x.ts)}</span><span>{x.kind}</span><span className="truncate">{x.what}</span><span className="tabular-nums">{x.amount != null ? won(x.amount) : ""}</span>
                </li>
              ))}
            </ol>
          </More>
          <More title={`함께 볼 거래 · ${related.length}건`} disabled={!related.length}>
            <ul className="flex flex-col gap-1">
              {related.map((r) => (
                <li key={r.tx_id} className="grid grid-cols-[6rem_1fr_auto] gap-x-3 text-sm"><span className="type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</span><span className="truncate">{r.merchant} · {r.mcc_name}</span><span className="tabular-nums">{won(r.total)}</span></li>
              ))}
            </ul>
          </More>
          <More title={`비슷한 사례 · ${c.precedents.cases.length}건`} disabled={!c.precedents.cases.length}>
            <ul className="flex flex-col gap-1.5">
              {c.precedents.cases.map((p) => (
                <li key={p.precedent_id} className="grid grid-cols-[1fr_auto] gap-x-3 text-sm"><span><span>{p.title}</span><div className="type-meta">{p.source} · 겹침 {p.overlap.map((r) => r.slice(0, 3)).join(", ")}</div></span><span className="type-meta tabular-nums">유사도 {p.score.toFixed(2)}</span></li>
              ))}
            </ul>
          </More>
          <More title="모델 점수" disabled={!c.score}>
            {c.score && (
              <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="type-meta">점수</dt><dd className="tabular-nums">{c.score.score_learned != null ? c.score.score_learned.toFixed(2) : "—"} <span className="type-meta">({c.score.learned_name ?? "기준선"} · 시연용)</span></dd>
                <dt className="type-meta">기여 피처</dt><dd>{c.score.top_features_learned.slice(0, 3).map((f) => f[2]).join(" · ")}</dd>
              </dl>
            )}
          </More>
        </div>
      </div>
      <VerdictBar current={lastReview?.decision} onVerdict={onVerdict} />
    </div>
  )
}

function More({ title, disabled, children }: { title: string; disabled?: boolean; children: ReactNode }) {
  return (
    <Collapsible disabled={disabled}>
      <CollapsibleTrigger className="group flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm text-muted-foreground hover:bg-surface-hover disabled:opacity-50 disabled:hover:bg-transparent">
        <span>{title}</span>
        <HugeiconsIcon icon={ArrowDown01Icon} strokeWidth={2} className="size-4 transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="px-2 pt-1 pb-3">{children}</CollapsibleContent>
    </Collapsible>
  )
}

function VerdictBar({ current, onVerdict }: { current?: Decision; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const [pending, setPending] = useState<Decision | null>(null)
  const [reason, setReason] = useState<string>("")
  const [memo, setMemo] = useState("")
  const label: Record<Decision, string> = { violation: "위반", ok: "아님", hold: "보류" }
  const pick = (d: Decision) => { if (d === "ok") { onVerdict?.(d); return } setPending(d); setReason(""); setMemo("") }
  const save = () => { if (pending) onVerdict?.(pending, reason || undefined, memo || undefined); setPending(null) }
  return (
    <div className="shrink-0 bg-surface-panel px-8 py-3">
      {pending ? (
        <div className="flex items-center gap-2">
          <span className={`type-label ${pending === "violation" ? "text-destructive" : ""}`}>{label[pending]}</span>
          <Select value={reason} onValueChange={setReason}>
            <SelectTrigger className="w-52" size="sm"><SelectValue placeholder={pending === "violation" ? "조치" : "사유"} /></SelectTrigger>
            <SelectContent>{mock.reason_codes.map((r) => <SelectItem key={r.code} value={r.code}>{r.label}</SelectItem>)}</SelectContent>
          </Select>
          <Input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="메모 (선택)" className="h-8 flex-1" onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setPending(null) }} />
          <Button size="sm" variant={pending === "violation" ? "destructive" : "default"} onClick={save}>저장 <Kbd>↵</Kbd></Button>
          <Button size="sm" variant="ghost" onClick={() => setPending(null)}>취소 <Kbd>Esc</Kbd></Button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Button variant="destructive" onClick={() => pick("violation")}>위반 <Kbd className="bg-transparent text-destructive-foreground/80">V</Kbd></Button>
          <Button variant="outline" onClick={() => pick("ok")}>아님 <Kbd>N</Kbd></Button>
          <Button variant="outline" onClick={() => pick("hold")}>보류 <Kbd>H</Kbd></Button>
          <span className="ml-auto type-meta">{current ? `현재 판정: ${label[current]}` : "저장 후 다음 건으로"} · 이동 <Kbd>J</Kbd> <Kbd>K</Kbd></span>
        </div>
      )}
    </div>
  )
}
