import { lazy, Suspense, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { conclusion } from "@/lib/conclusion"
import { finding } from "@/lib/findings"
import { mock, won, hhmm, mmdd } from "@/mock"
import type { CaseBundle, Decision, QueueSource } from "@/types"

const AmountDistribution = lazy(() => import("@/components/charts/amount-distribution").then((m) => ({ default: m.AmountDistribution })))
const DayTimeline = lazy(() => import("@/components/charts/day-timeline").then((m) => ({ default: m.DayTimeline })))
const HistoryWeeks = lazy(() => import("@/components/charts/history-weeks").then((m) => ({ default: m.HistoryWeeks })))
const Fallback = <div className="h-20 animate-pulse rounded-lg bg-surface-panel" />

/**
 * Case panel v2 (docs/REVIEW_SCREEN.md): the transaction as an object — property grid (facts once), one conclusion line,
 * the amount-distribution chart, a findings table (observed vs baseline), relation tabs, verdict bar with provenance.
 * No prose paragraphs, no repeated facts, no lines (docs/DESIGN.md).
 */
export function CasePanel({ c, source, onVerdict }: { c: CaseBundle; source?: QueueSource; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const t = c.transaction
  const vio = c.evidences.filter((e) => e.severity === "violation").length, adv = c.evidences.length - vio
  const related = c.evidences.flatMap((e) => e.related_tx)
  const place = c.timeline.find((x) => x.focal)?.place
  const dow = (t.weekday as string | undefined) ?? ""
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-8 pt-6 pb-6">
        {/* Property grid: every fact exactly once */}
        <dl className="grid grid-cols-[4.5rem_1fr_4.5rem_1fr] gap-x-3 gap-y-1.5 text-sm">
          <dt className="type-meta">금액</dt><dd className="text-base font-semibold tabular-nums">{won(t.total)}</dd>
          <dt className="type-meta">일시</dt><dd>{t.tx_ts.slice(0, 10)}{dow ? ` (${dow})` : ""} {hhmm(t.tx_ts)}</dd>
          <dt className="type-meta">가맹점</dt><dd className="truncate">{t.merchant}</dd>
          <dt className="type-meta">업종</dt><dd className="truncate">{t.mcc_name ?? "—"}{place ? ` · ${place}` : ""}</dd>
          <dt className="type-meta">사용자</dt><dd className="truncate">{t.emp_name} · {t.dept}{t.rank ? ` · ${t.rank}` : ""}</dd>
          <dt className="type-meta">승인자</dt><dd className="truncate">{String(t.approver ?? "—")}</dd>
          <dt className="type-meta">계정</dt><dd>{t.account_policy}</dd>
          <dt className="type-meta">전표</dt><dd className="truncate tabular-nums">{String(t.sap_doc_no ?? "—")} · 첨부 {t.has_attachment ? "있음" : "없음"}{t.memo ? ` · "${String(t.memo).slice(0, 24)}"` : ""}</dd>
        </dl>

        {/* Conclusion line + severity counts */}
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="text-base font-semibold">{conclusion(c, source)}</span>
          {vio > 0 && <Badge variant="destructive">위반 {vio}</Badge>}
          {adv > 0 && <Badge variant="outline">참고 {adv}</Badge>}
        </div>

        {/* Q1: how unusual is the amount */}
        <Suspense fallback={Fallback}><AmountDistribution profile={c.profile} peerPercentile={c.context.peer?.percentile_of_this} className="mt-4 rounded-lg bg-surface-panel px-4 py-3" /></Suspense>

        {/* Findings: observed vs baseline */}
        {c.evidences.length > 0 && (
          <Table className="mt-4">
            <TableHeader>
              <TableRow className="border-0 hover:bg-transparent">
                <TableHead className="w-12 type-meta">등급</TableHead><TableHead className="w-40 type-meta">규칙</TableHead>
                <TableHead className="type-meta">관측값</TableHead><TableHead className="type-meta">기준</TableHead><TableHead className="w-56 type-meta">근거</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {c.evidences.map((e) => { const f = finding(e); return (
                <TableRow key={e.rule_id} className="border-0 hover:bg-surface-hover">
                  <TableCell className={`font-semibold ${e.severity === "violation" ? "text-destructive" : "text-muted-foreground"}`}>{e.severity === "violation" ? "위반" : "참고"}</TableCell>
                  <TableCell className="font-medium">{e.rule_name}</TableCell>
                  <TableCell>{f.observed}</TableCell>
                  <TableCell className="text-muted-foreground">{f.baseline}</TableCell>
                  <TableCell className="type-meta truncate" title={e.citation}>{e.citation}</TableCell>
                </TableRow>
              ) })}
            </TableBody>
          </Table>
        )}

        {/* Relations */}
        <Tabs defaultValue="day" className="mt-6">
          <TabsList variant="line">
            <TabsTrigger value="day">그날</TabsTrigger>
            <TabsTrigger value="person">이 사람</TabsTrigger>
            <TabsTrigger value="approver">승인자</TabsTrigger>
            <TabsTrigger value="precedents">비슷한 사례{c.precedents.cases.length ? ` ${c.precedents.cases.length}` : ""}</TabsTrigger>
            <TabsTrigger value="related">함께 볼 거래{related.length ? ` ${related.length}` : ""}</TabsTrigger>
            <TabsTrigger value="model">모델</TabsTrigger>
          </TabsList>
          <TabsContent value="day" className="pt-3">
            <Suspense fallback={Fallback}><DayTimeline c={c} /></Suspense>
          </TabsContent>
          <TabsContent value="person" className="pt-3">
            <Suspense fallback={Fallback}><HistoryWeeks profile={c.profile} /></Suspense>
            <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="type-meta">과거 거래</dt><dd className="tabular-nums">{c.profile.amount.user.n}건 · 적중 {c.context.history.flagged_tx}건 · 위반 확정 {c.context.history.violations} · 아님 {c.context.history.cleared}</dd>
              <dt className="type-meta">최근 거래</dt><dd className="type-meta">{c.context.recent_tx.slice(0, 5).map((r) => `${mmdd(r.tx_ts)} ${r.merchant} ${won(r.total)}${r.rules.length ? ` (적중 ${r.rules.length})` : ""}`).join(" · ")}</dd>
            </dl>
          </TabsContent>
          <TabsContent value="approver" className="pt-3">
            <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="type-meta">승인자</dt><dd>{String(t.approver ?? "—")}{t.approver_id ? ` · ${String(t.approver_id)}` : ""}</dd>
              <dt className="type-meta">관계</dt><dd>{c.evidences.some((e) => e.rule_id.startsWith("R18")) ? "승인자 주거지와 가맹점이 같은 시군구 (R18)" : "특이 관계 없음"}</dd>
            </dl>
          </TabsContent>
          <TabsContent value="precedents" className="pt-3">
            {c.precedents.cases.length ? (
              <ul className="flex flex-col gap-2 text-sm">
                {c.precedents.cases.map((p) => (
                  <li key={p.precedent_id} className="grid grid-cols-[1fr_auto] gap-x-3"><span><span className="font-medium">{p.title}</span><div className="type-meta">{p.source} · 겹침 {p.overlap.map((r) => r.slice(0, 3)).join(", ")}{p.only_in_tx.length ? ` · 이 건에만 ${p.only_in_tx.map((r) => r.slice(0, 3)).join(", ")}` : ""}</div></span><span className="type-meta tabular-nums">유사도 {p.score.toFixed(2)}</span></li>
                ))}
                <li className="type-meta">같은 규칙 조합 과거 판정: 위반 {c.precedents.summary.violation} · 아님 {c.precedents.summary.ok}</li>
              </ul>
            ) : <p className="type-meta">겹치는 선례 없음</p>}
          </TabsContent>
          <TabsContent value="related" className="pt-3">
            {related.length ? (
              <ul className="flex flex-col gap-1 text-sm">{related.map((r) => <li key={r.tx_id} className="grid grid-cols-[6rem_1fr_auto] gap-x-3"><span className="type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</span><span className="truncate">{r.merchant} · {r.mcc_name}</span><span className="tabular-nums">{won(r.total)}</span></li>)}</ul>
            ) : <p className="type-meta">분할·동시간 상대 거래 없음</p>}
          </TabsContent>
          <TabsContent value="model" className="pt-3">
            {c.score ? (
              <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="type-meta">점수</dt><dd className="tabular-nums">{c.score.score_learned != null ? c.score.score_learned.toFixed(2) : "—"} <span className="type-meta">({c.score.learned_name ?? "기준선"} · 시연용, 순서 참고만)</span></dd>
                <dt className="type-meta">기여 피처</dt><dd>{c.score.top_features_learned.slice(0, 3).map((f) => f[2]).join(" · ")}</dd>
              </dl>
            ) : <p className="type-meta">점수 없음</p>}
          </TabsContent>
        </Tabs>
      </div>
      <VerdictBar current={c.reviews[0]?.decision} provenance={`규칙 v${c.evidences[0]?.rule_version ?? 2}${c.score ? ` · 모델 ${c.score.model_version}` : ""} · 큐 ${mock.period.period_from.slice(0, 7)}`} onVerdict={onVerdict} />
    </div>
  )
}

function VerdictBar({ current, provenance, onVerdict }: { current?: Decision; provenance: string; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
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
          {current && <span className="ml-2 type-meta">현재 판정 {label[current]}</span>}
          <span className="ml-auto type-meta">{provenance} · 이동 <Kbd>J</Kbd> <Kbd>K</Kbd></span>
        </div>
      )}
    </div>
  )
}
