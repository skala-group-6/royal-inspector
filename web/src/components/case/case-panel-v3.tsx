import { lazy, Suspense, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon, ArrowDown01Icon, ArrowRight01Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Kbd } from "@/components/ui/kbd"
import { humanLine } from "@/lib/copy"
import { finding } from "@/lib/findings"
import { won, hhmm, mmdd } from "@/lib/format"
import type { CaseBundle, Decision, QueueSource } from "@/types"

const AmountDistribution = lazy(() => import("@/components/charts/amount-distribution").then((m) => ({ default: m.AmountDistribution })))
const DayTimeline = lazy(() => import("@/components/charts/day-timeline").then((m) => ({ default: m.DayTimeline })))
const HistoryWeeks = lazy(() => import("@/components/charts/history-weeks").then((m) => ({ default: m.HistoryWeeks })))
const Fallback = <div className="h-20 animate-pulse rounded-lg bg-surface-panel" />

/**
 * Proposal v3 — "넘기는 화면": three layers, each one more click away.
 *   0–3 s   one plain sentence + the amount + who/where
 *   3–10 s  one line per rule: observed | baseline (citation on expand)
 *   on demand  details, folded; a section opens by itself only when a rule needs it. Empty sections are not rendered.
 * Words only where a control cannot say it: chevrons for fold state, count badges for "how many", the pressed button for the current verdict.
 */
export function CasePanelV3({ c, source, onVerdict }: { c: CaseBundle; source?: QueueSource; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const t = c.transaction
  const rules = new Set(c.evidences.map((e) => e.rule_id.slice(0, 3)))
  const { head, tail } = humanLine(c, source)
  const vio = c.evidences.filter((e) => e.severity === "violation").length
  const related = c.evidences.flatMap((e) => e.related_tx)
  const needDay = rules.has("R06") || rules.has("R12") || rules.has("R02") || rules.has("R01")
  const needAmount = rules.has("R16") || rules.has("R03") || rules.has("R04") || rules.has("R21")
  const current = c.reviews[0]?.decision
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-8 pt-7 pb-6">
        {/* Layer 1 */}
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold leading-snug">{head}{tail ? <span className="text-muted-foreground">. {tail}</span> : ""}</h2>
            <p className="mt-1.5 truncate type-meta">{t.emp_name} · {t.dept}{t.rank ? ` · ${t.rank}` : ""} · {mmdd(t.tx_ts)} {hhmm(t.tx_ts)}{t.weekday ? ` (${String(t.weekday)})` : ""} · {t.merchant}</p>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-2xl font-semibold tabular-nums">{won(t.total)}</div>
            {vio > 0 && <Badge variant="destructive" className="mt-1">위반 {vio}</Badge>}
          </div>
        </div>

        {/* Layer 2 */}
        {c.evidences.length > 0 && <ul className="mt-6 flex flex-col gap-0.5">{c.evidences.map((e) => <RuleLine key={e.rule_id} e={e} />)}</ul>}

        {/* Amount, as a sentence and one scale */}
        {c.profile.amount.user.n > 0 && (
          <div className="mt-6">
            <AmountSimple c={c} />
            <Section title="금액 분포 상세" open={needAmount} nested>
              <Suspense fallback={Fallback}><AmountDistribution profile={c.profile} peerPercentile={c.context.peer?.percentile_of_this} className="rounded-lg bg-surface-panel px-4 py-3" /></Suspense>
            </Section>
          </div>
        )}

        {/* Layer 3: only sections that have something */}
        <div className="mt-4 flex flex-col gap-0.5">
          {(c.timeline.length > 1 || c.context.access_same_day.length > 0) && (
            <Section title="그날 동선" count={c.context.access_same_day.length + Math.max(0, c.timeline.filter((x) => x.kind === "카드").length - 1)} open={needDay}>
              <Suspense fallback={Fallback}><DayTimeline c={c} /></Suspense>
            </Section>
          )}
          {related.length > 0 && (
            <Section title="연결된 결제" count={related.length} open>
              <ul className="flex flex-col gap-1 text-sm">{related.map((r) => <li key={r.tx_id} className="grid grid-cols-[6rem_1fr_auto] gap-x-3"><span className="type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</span><span className="truncate">{r.merchant} · {r.mcc_name}</span><span className="tabular-nums">{won(r.total)}</span></li>)}</ul>
            </Section>
          )}
          <Section title="이 사용자 이력" count={c.context.history.flagged_tx}>
            <p className="mb-2 text-sm">과거 결제 {c.profile.amount.user.n}건 · 규칙에 걸림 {c.context.history.flagged_tx}회 · 위반 판정 {c.context.history.violations}회 · 아님 판정 {c.context.history.cleared}회</p>
            <Suspense fallback={Fallback}><HistoryWeeks profile={c.profile} /></Suspense>
          </Section>
          {c.precedents.cases.length > 0 && (
            <Section title="과거 징계 사례" count={c.precedents.cases.length}>
              <ul className="flex flex-col gap-1.5 text-sm">{c.precedents.cases.map((p) => <li key={p.precedent_id}><span className="font-medium">{p.title}</span> <span className="type-meta">{p.source}</span></li>)}</ul>
            </Section>
          )}
          <Section title="전표 정보">
            <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="type-meta">전표</dt><dd className="tabular-nums">{String(t.sap_doc_no ?? "—")} · 첨부 {t.has_attachment ? "있음" : "없음"}</dd>
              <dt className="type-meta">계정</dt><dd>{t.account_policy}</dd>
              <dt className="type-meta">승인자</dt><dd>{String(t.approver ?? "—")}</dd>
              <dt className="type-meta">적요</dt><dd>{t.memo ? String(t.memo) : "—"}</dd>
              {c.score && <><dt className="type-meta">모델</dt><dd className="type-meta">{c.score.learned_name ?? "기준선"} {c.score.score_learned?.toFixed(2) ?? ""} · {c.score.top_features_learned.slice(0, 2).map((f) => f[2]).join(" · ")}</dd></>}
            </dl>
          </Section>
        </div>
      </div>
      {/* Verdict bar: buttons only; the current verdict is the pressed one */}
      <div className="flex shrink-0 items-center gap-2 bg-surface-panel px-8 py-3">
        <Button variant={current === "violation" ? "destructive" : "outline"} className={current === "violation" ? "" : "text-destructive"} onClick={() => onVerdict?.("violation")}>위반 <Kbd>V</Kbd></Button>
        <Button variant={current === "ok" ? "default" : "outline"} onClick={() => onVerdict?.("ok")}>아님 <Kbd>N</Kbd></Button>
        <Button variant={current === "hold" ? "default" : "outline"} onClick={() => onVerdict?.("hold")}>보류 <Kbd>H</Kbd></Button>
      </div>
    </div>
  )
}

/** "이 사람 평소의 12배, 동료 100명 중 6등 금액" + one log scale with the user's usual amount, the peer band and this amount. */
function AmountSimple({ c }: { c: CaseBundle }) {
  const { user, peer } = c.profile.amount; const total = c.transaction.total
  const ratio = user.p50 ? total / user.p50 : null
  const pct = c.context.peer?.percentile_of_this
  const rankTxt = pct != null ? `동료 100명 중 ${Math.max(1, Math.round(100 - pct))}등` : null
  const parts = [ratio != null ? `이 사람 평소의 ${ratio >= 10 ? Math.round(ratio) : ratio.toFixed(1)}배` : null, rankTxt].filter(Boolean)
  const vals = [user.p50, peer.p25, peer.p75, total].filter((v): v is number => v != null && v > 0)
  const lo = Math.min(...vals) / 1.6, hi = Math.max(...vals) * 1.3
  const x = (v: number) => `${((Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo))) * 100}%`
  return (
    <div className="rounded-lg bg-surface-panel px-4 py-3">
      <p className="text-sm font-medium">{parts.length ? `${parts.join(", ")} 금액` : "비교할 과거 기록이 적음"}</p>
      <div className="relative mt-3 h-6">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-foreground/10" />
        {peer.p25 != null && peer.p75 != null && <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-foreground/25" style={{ left: x(peer.p25), width: `calc(${x(peer.p75)} - ${x(peer.p25)})` }} title="동료 보통 범위" />}
        {user.p50 != null && <div className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/70 ring-2 ring-surface-panel" style={{ left: x(user.p50) }} title="이 사람 평소" />}
        <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-destructive ring-2 ring-surface-panel" style={{ left: x(total) }} title="이 건" />
      </div>
      <div className="relative mt-1 h-4 type-meta">
        {user.p50 != null && <span className="absolute -translate-x-1/2" style={{ left: x(user.p50) }}>평소 {won(user.p50)}</span>}
        <span className="absolute -translate-x-1/2 font-medium text-foreground" style={{ left: x(total) }}>이 건</span>
      </div>
    </div>
  )
}

function RuleLine({ e }: { e: CaseBundle["evidences"][number] }) {
  const [open, setOpen] = useState(false); const f = finding(e); const v = e.severity === "violation"
  return (
    <li>
      <button type="button" onClick={() => setOpen((o) => !o)} className="grid w-full grid-cols-[1.25rem_9rem_1fr_1fr] items-baseline gap-x-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover" aria-expanded={open}>
        <span className={`inline-flex items-center ${v ? "text-destructive" : "text-muted-foreground"}`} title={v ? "위반 가능" : "주의"}>
          <HugeiconsIcon icon={v ? Alert02Icon : InformationCircleIcon} strokeWidth={2} className="size-3.5" /><span className="sr-only">{v ? "위반" : "주의"}</span>
        </span>
        <span className="truncate font-medium">{e.rule_name}</span>
        <span className="truncate">{f.observed}</span>
        <span className="truncate text-muted-foreground">{f.baseline}</span>
      </button>
      {open && <p className="px-3 pb-2 pl-[13.5rem] type-meta">{e.citation || e.explain}</p>}
    </li>
  )
}

function Section({ title, count, open = false, nested = false, children }: { title: string; count?: number; open?: boolean; nested?: boolean; children: React.ReactNode }) {
  const [isOpen, setOpen] = useState(open)
  return (
    <Collapsible open={isOpen} onOpenChange={setOpen}>
      <CollapsibleTrigger className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-surface-hover ${nested ? "type-meta" : "text-sm font-medium"}`}>
        <HugeiconsIcon icon={isOpen ? ArrowDown01Icon : ArrowRight01Icon} strokeWidth={2} className="size-3.5 text-muted-foreground" />
        <span>{title}</span>
        {count ? <Badge variant="outline" className="h-4 px-1.5 text-[10px] tabular-nums">{count}</Badge> : null}
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pt-1 pb-3">{children}</CollapsibleContent>
    </Collapsible>
  )
}
