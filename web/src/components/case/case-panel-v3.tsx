import { lazy, Suspense, useState } from "react"
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
 *   3–10 s  one line per rule: observed vs baseline (citation on expand)
 *   on demand  details, folded; a section opens by itself only when a rule needs it (R06/R12 → that day, R03/R06 → related, R16 → amount)
 * Verdict bar stays where it is. Keyboard first (N/V/H, J/K).
 */
export function CasePanelV3({ c, source, onVerdict }: { c: CaseBundle; source?: QueueSource; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const t = c.transaction
  const rules = new Set(c.evidences.map((e) => e.rule_id.slice(0, 3)))
  const { head, tail } = humanLine(c, source)
  const vio = c.evidences.filter((e) => e.severity === "violation").length, adv = c.evidences.length - vio
  const related = c.evidences.flatMap((e) => e.related_tx)
  const needDay = rules.has("R06") || rules.has("R12") || rules.has("R02") || rules.has("R01")
  const needRelated = related.length > 0
  const needAmount = rules.has("R16") || rules.has("R03") || rules.has("R04") || rules.has("R21")
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-8 pt-7 pb-6">
        {/* Layer 1: the sentence, the amount, who/where */}
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold leading-snug">{head}{tail ? <span className="text-muted-foreground">. {tail}</span> : ""}</h2>
            <p className="mt-1.5 truncate type-meta">{t.emp_name} · {t.dept}{t.rank ? ` · ${t.rank}` : ""} · {mmdd(t.tx_ts)} {hhmm(t.tx_ts)}{t.weekday ? ` (${String(t.weekday)})` : ""} · {t.merchant}</p>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-2xl font-semibold tabular-nums">{won(t.total)}</div>
            <div className="mt-1 flex justify-end gap-1">
              {vio > 0 && <Badge variant="destructive">위반 {vio}</Badge>}
              {adv > 0 && <Badge variant="outline">참고 {adv}</Badge>}
            </div>
          </div>
        </div>

        {/* Layer 2: one line per rule */}
        {c.evidences.length > 0 && (
          <ul className="mt-6 flex flex-col gap-1">
            {c.evidences.map((e) => <RuleLine key={e.rule_id} e={e} />)}
          </ul>
        )}
        {!c.evidences.length && <p className="mt-6 rounded-lg bg-surface-panel px-4 py-3 text-sm text-muted-foreground">규칙에 걸리지 않은 건입니다. 아래 상세는 필요할 때만 펼쳐 보세요.</p>}

        {/* Layer 3: details, folded unless a rule asks for them */}
        <div className="mt-6 flex flex-col gap-1">
          <Section title="금액이 평소와 다른가" hint={c.profile.amount.user.p50 ? `본인 중앙값 ${won(c.profile.amount.user.p50)} · ×${(t.total / c.profile.amount.user.p50).toFixed(1)}` : "본인 과거 기록 없음"} open={needAmount}>
            <Suspense fallback={Fallback}><AmountDistribution profile={c.profile} peerPercentile={c.context.peer?.percentile_of_this} className="rounded-lg bg-surface-panel px-4 py-3" /></Suspense>
          </Section>
          <Section title="그날 무슨 일이 있었나" hint={c.context.access_same_day.length ? `출입 ${c.context.access_same_day.length}건` : "사옥 출입 기록 없음"} open={needDay}>
            <Suspense fallback={Fallback}><DayTimeline c={c} /></Suspense>
          </Section>
          <Section title="함께 볼 거래" hint={related.length ? `${related.length}건` : "없음"} open={needRelated}>
            {related.length ? <ul className="flex flex-col gap-1 text-sm">{related.map((r) => <li key={r.tx_id} className="grid grid-cols-[6rem_1fr_auto] gap-x-3"><span className="type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</span><span className="truncate">{r.merchant} · {r.mcc_name}</span><span className="tabular-nums">{won(r.total)}</span></li>)}</ul> : <p className="type-meta">분할·동시간 상대 거래 없음</p>}
          </Section>
          <Section title="이 사람은 평소 어떤가" hint={`과거 ${c.profile.amount.user.n}건 · 적중 ${c.context.history.flagged_tx} · 위반 확정 ${c.context.history.violations}`}>
            <Suspense fallback={Fallback}><HistoryWeeks profile={c.profile} /></Suspense>
          </Section>
          <Section title="비슷한 사례" hint={c.precedents.cases.length ? `${c.precedents.cases.length}건` : "없음"}>
            {c.precedents.cases.length ? <ul className="flex flex-col gap-1.5 text-sm">{c.precedents.cases.map((p) => <li key={p.precedent_id}><span className="font-medium">{p.title}</span> <span className="type-meta">{p.source} · 유사도 {p.score.toFixed(2)}</span></li>)}</ul> : <p className="type-meta">겹치는 선례 없음</p>}
          </Section>
          <Section title="전표·승인" hint={`${String(t.sap_doc_no ?? "—")} · 승인자 ${String(t.approver ?? "—")} · 첨부 ${t.has_attachment ? "있음" : "없음"}`}>
            <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="type-meta">계정</dt><dd>{t.account_policy}</dd>
              <dt className="type-meta">적요</dt><dd>{t.memo ? String(t.memo) : "—"}</dd>
              <dt className="type-meta">모델</dt><dd className="type-meta">{c.score ? `${c.score.learned_name ?? "기준선"} ${c.score.score_learned?.toFixed(2) ?? ""} · ${c.score.top_features_learned.slice(0, 2).map((f) => f[2]).join(" · ")}` : "점수 없음"}</dd>
            </dl>
          </Section>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 bg-surface-panel px-8 py-3">
        <Button variant="destructive" onClick={() => onVerdict?.("violation")}>위반 <Kbd className="bg-transparent text-destructive-foreground/80">V</Kbd></Button>
        <Button variant="outline" onClick={() => onVerdict?.("ok")}>아님 <Kbd>N</Kbd></Button>
        <Button variant="outline" onClick={() => onVerdict?.("hold")}>보류 <Kbd>H</Kbd></Button>
        {c.reviews[0] && <span className="ml-2 type-meta">현재 판정 {({ violation: "위반", ok: "아님", hold: "보류" })[c.reviews[0].decision]}</span>}
        <span className="ml-auto type-meta">저장하면 다음 건으로 · 이동 <Kbd>J</Kbd> <Kbd>K</Kbd></span>
      </div>
    </div>
  )
}

function RuleLine({ e }: { e: CaseBundle["evidences"][number] }) {
  const [open, setOpen] = useState(false); const f = finding(e)
  return (
    <li>
      <button type="button" onClick={() => setOpen((o) => !o)} className="grid w-full grid-cols-[2.5rem_9rem_1fr] items-baseline gap-x-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover">
        <span className={`font-semibold ${e.severity === "violation" ? "text-destructive" : "text-muted-foreground"}`}>{e.severity === "violation" ? "위반" : "참고"}</span>
        <span className="truncate font-medium">{e.rule_name}</span>
        <span className="truncate">{f.observed} <span className="text-muted-foreground">· 기준 {f.baseline}</span></span>
      </button>
      {open && <p className="px-3 pb-2 pl-[15.5rem] type-meta">{e.citation || e.explain}</p>}
    </li>
  )
}

function Section({ title, hint, open = false, children }: { title: string; hint?: string; open?: boolean; children: React.ReactNode }) {
  const [isOpen, setOpen] = useState(open)
  return (
    <Collapsible open={isOpen} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex w-full items-baseline justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-hover">
        <span className="font-medium">{title}</span>
        <span className="truncate type-meta">{hint}{isOpen ? "" : " · 펼치기"}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pt-1 pb-3">{children}</CollapsibleContent>
    </Collapsible>
  )
}
