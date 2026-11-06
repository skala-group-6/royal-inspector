import { lazy, Suspense, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowRight01Icon } from "@hugeicons/core-free-icons"
import { won, hhmm, mmdd } from "@/lib/format"
import type { CaseBundle } from "@/types"

const HistoryWeeks = lazy(() => import("@/components/charts/history-weeks").then((m) => ({ default: m.HistoryWeeks })))
const Fallback = <div className="h-16 animate-pulse rounded-lg bg-surface-panel" />

/** Shared, folded: things that are true of every case and rarely decide one — user history, linked transactions, voucher. */
export function More({ c }: { c: CaseBundle }) {
  const t = c.transaction; const related = c.evidences.flatMap((e) => e.related_tx)
  return (
    <div data-slot="case-more" className="flex flex-col gap-0.5">
      <Section title="이 사용자 이력" count={c.context.history.flagged_tx}>
        <p className="mb-2 text-sm">과거 결제 {c.profile.amount.user.n}건 · 규칙에 걸림 {c.context.history.flagged_tx}회 · 위반 판정 {c.context.history.violations}회 · 아님 판정 {c.context.history.cleared}회</p>
        <Suspense fallback={Fallback}><HistoryWeeks profile={c.profile} /></Suspense>
      </Section>
      {related.length > 0 && (
        <Section title="연결된 결제" count={related.length}>
          <ul className="flex flex-col gap-1 text-sm">{related.map((r) => <li key={r.tx_id} className="grid grid-cols-[6rem_1fr_auto] gap-x-3"><span className="type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</span><span className="truncate">{r.merchant} · {r.mcc_name}</span><span className="tabular-nums">{won(r.total)}</span></li>)}</ul>
        </Section>
      )}
      <Section title="전표 정보">
        <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="type-meta">전표</dt><dd className="tabular-nums">{String(t.sap_doc_no ?? "—")} · 첨부 {t.has_attachment ? "있음" : "없음"}</dd>
          <dt className="type-meta">계정</dt><dd>{t.account_policy}</dd>
          <dt className="type-meta">승인자</dt><dd>{String(t.approver ?? "—")}</dd>
          <dt className="type-meta">적요</dt><dd>{t.memo ? String(t.memo) : "—"}</dd>
        </dl>
      </Section>
    </div>
  )
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium hover:bg-surface-hover">
        <HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} className="size-3.5 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
        <span>{title}</span>
        {count ? <Badge variant="outline" className="h-4 px-1.5 text-[10px] tabular-nums">{count}</Badge> : null}
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pt-1 pb-3">{children}</CollapsibleContent>
    </Collapsible>
  )
}
