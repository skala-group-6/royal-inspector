import { lazy, Suspense, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert02Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { humanLine, claimFor } from "@/lib/copy"
import { finding } from "@/lib/findings"
import { won, hhmm, mmdd } from "@/lib/format"
import type { CaseBundle, Decision, Evidence, QueueSource } from "@/types"

const AmountBars = lazy(() => import("@/components/charts/amount-bars").then((m) => ({ default: m.AmountBars })))
const AmountDots = lazy(() => import("@/components/charts/amount-dots").then((m) => ({ default: m.AmountDots })))
const DayTimeline = lazy(() => import("@/components/charts/day-timeline").then((m) => ({ default: m.DayTimeline })))
const HistoryWeeks = lazy(() => import("@/components/charts/history-weeks").then((m) => ({ default: m.HistoryWeeks })))
const Fallback = <div className="h-16 animate-pulse rounded-lg bg-surface-panel" />

/**
 * Proposal v4 — one card per finding, every card in the same grammar (domain-agnostic):
 *   ① claim   one plain sentence + severity icon
 *   ② facts   observed | baseline
 *   ③ materials  chips for the evidence this finding needs (only what exists); a chip unfolds inside the card
 *   ④ basis   policy line or precedent, small
 *   ⑤ judgment  per-finding state (문제 / 소명 / 확인) — optional, feeds the recommendation in the verdict bar
 * Cards are ordered by severity; shared context (user history, precedents, voucher) folds under the cards.
 * The pack decides which materials a rule needs (MATERIALS below); the card itself knows nothing about cards or cards' rules.
 */
type MaterialKey = "day" | "related" | "amount" | "recent" | "policy" | "access"
const MATERIALS: Record<string, MaterialKey[]> = {   // rule prefix → materials that help judge it (pack knowledge; move to the pack later)
  R01: ["day", "policy"], R02: ["day", "policy"], R03: ["related", "amount"], R04: ["amount", "policy"], R05: ["day", "policy"], R06: ["related", "day"],
  R07: ["day", "policy"], R08: ["policy"], R09: ["related", "recent"], R10: ["policy"], R11: ["policy"], R12: ["access", "day"], R13: ["policy", "recent"],
  R14: ["policy"], R15: ["day"], R16: ["amount", "recent"], R17: ["day", "policy"], R18: ["day", "policy"], R21: ["policy", "recent"],
}
const LABEL: Record<MaterialKey, string> = { day: "그날 동선", related: "연결된 결제", amount: "금액 비교", recent: "최근 거래", policy: "규정", access: "출입 기록" }
type Judg = "problem" | "explained" | "checked" | undefined

export function CasePanelV4({ c, source, onVerdict }: { c: CaseBundle; source?: QueueSource; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  const t = c.transaction
  const { head, tail } = humanLine(c, source)
  const vio = c.evidences.filter((e) => e.severity === "violation").length
  const [judg, setJudg] = useState<Record<string, Judg>>({})
  const problems = Object.values(judg).filter((j) => j === "problem").length
  const explained = Object.values(judg).filter((j) => j === "explained").length
  const sorted = [...c.evidences].sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "violation" ? -1 : 1))
  const current = c.reviews[0]?.decision
  const available = (k: MaterialKey) => ({
    day: c.timeline.length > 0, related: c.evidences.some((e) => e.related_tx.length > 0), amount: c.profile.amount.user.n > 0 || c.profile.amount.peer.n > 0,
    recent: c.context.recent_tx.length >= 3, policy: !!c.policy, access: c.context.access_same_day.length > 0,
  })[k]
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-8 pt-7 pb-6">
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

        <div className="mt-5 flex flex-col gap-2">
          {sorted.map((e) => (
            <FindingCard key={e.rule_id} e={e} c={c} materials={(MATERIALS[e.rule_id.slice(0, 3)] ?? []).filter(available)} judg={judg[e.rule_id]} onJudg={(j) => setJudg((s) => ({ ...s, [e.rule_id]: j }))} />
          ))}
          {!sorted.length && (
            <div className="rounded-xl bg-surface-panel px-4 py-3 text-sm">
              <p className="font-medium">걸린 규칙 없음</p>
              <p className="mt-1 type-meta">{source === "model" ? "모델이 평소와 다르다고 본 건입니다. 금액 비교와 최근 거래를 보세요." : "무작위 표본입니다. 대부분 '아님'이 정상이며, 여기서 나오는 위반이 규칙이 놓친 것을 알려줍니다."}</p>
              <Suspense fallback={Fallback}><AmountBars profile={c.profile} className="mt-3" /></Suspense>
            </div>
          )}
        </div>

        <Shared c={c} />
      </div>
      <div className="flex shrink-0 items-center gap-2 bg-surface-panel px-8 py-3">
        <Button variant={current === "violation" ? "destructive" : "outline"} className={current === "violation" ? "" : "text-destructive"} onClick={() => onVerdict?.("violation")}>위반 <Kbd>V</Kbd></Button>
        <Button variant={current === "ok" ? "default" : "outline"} onClick={() => onVerdict?.("ok")}>아님 <Kbd>N</Kbd></Button>
        <Button variant={current === "hold" ? "default" : "outline"} onClick={() => onVerdict?.("hold")}>보류 <Kbd>H</Kbd></Button>
        <span className="ml-auto type-meta">{problems ? `문제 요소 ${problems}개 → 위반 권고` : explained && explained === Object.keys(judg).length && sorted.length ? "모두 소명됨 → 아님 권고" : "요소별 판단은 선택"}</span>
      </div>
    </div>
  )
}

function FindingCard({ e, c, materials, judg, onJudg }: { e: Evidence; c: CaseBundle; materials: MaterialKey[]; judg: Judg; onJudg: (j: Judg) => void }) {
  const [open, setOpen] = useState<MaterialKey | null>(null)
  const f = finding(e); const v = e.severity === "violation"
  return (
    <section className="rounded-xl bg-surface-panel px-4 py-3">
      {/* ① claim + ⑤ judgment */}
      <div className="flex items-center gap-2">
        <span className={v ? "text-destructive" : "text-muted-foreground"} title={v ? "위반 가능" : "주의"}><HugeiconsIcon icon={v ? Alert02Icon : InformationCircleIcon} strokeWidth={2} className="size-4" /></span>
        <span className="flex-1 truncate text-sm font-semibold">{claimFor(e, c)}</span>
        <ToggleGroup type="single" size="sm" variant="outline" value={judg ?? ""} onValueChange={(val) => onJudg((val || undefined) as Judg)} className="shrink-0">
          <ToggleGroupItem value="problem" className="h-6 px-2 text-[11px] data-[state=on]:bg-destructive data-[state=on]:text-destructive-foreground">문제</ToggleGroupItem>
          <ToggleGroupItem value="explained" className="h-6 px-2 text-[11px]">소명</ToggleGroupItem>
          <ToggleGroupItem value="checked" className="h-6 px-2 text-[11px]">확인</ToggleGroupItem>
        </ToggleGroup>
      </div>
      {/* ② facts */}
      <div className="mt-2 grid grid-cols-2 gap-x-4 pl-6 text-sm">
        <span className="truncate">{f.observed}</span>
        <span className="truncate text-muted-foreground">{f.baseline}</span>
      </div>
      {/* ③ materials */}
      {materials.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1 pl-6">
          {materials.map((m) => <Badge key={m} variant={open === m ? "default" : "outline"} className="cursor-pointer" onClick={() => setOpen(open === m ? null : m)}>{LABEL[m]}{count(m, c) ? ` ${count(m, c)}` : ""}</Badge>)}
        </div>
      )}
      {open && <div className="mt-2 pl-6"><Material k={open} c={c} e={e} /></div>}
      {/* ④ basis */}
      {(e.citation || e.explain) && <p className="mt-2 truncate pl-6 type-meta" title={e.citation || e.explain}>{e.citation || e.explain}</p>}
    </section>
  )
}

function count(k: MaterialKey, c: CaseBundle): number | undefined {
  if (k === "related") return c.evidences.reduce((n, e) => n + e.related_tx.length, 0) || undefined
  if (k === "recent") return c.context.recent_tx.length || undefined
  if (k === "access") return c.context.access_same_day.length || undefined
  return undefined
}

function Material({ k, c, e }: { k: MaterialKey; c: CaseBundle; e: Evidence }) {
  if (k === "day" || k === "access") return <Suspense fallback={Fallback}><DayTimeline c={c} /></Suspense>
  if (k === "amount") return <Suspense fallback={Fallback}><AmountBars profile={c.profile} /></Suspense>
  if (k === "recent") return <Suspense fallback={Fallback}><AmountDots c={c} /></Suspense>
  if (k === "related") {
    const rel = e.related_tx.length ? e.related_tx : c.evidences.flatMap((x) => x.related_tx)
    return <ul className="flex flex-col gap-1 text-sm">{rel.map((r) => <li key={r.tx_id} className="grid grid-cols-[6rem_1fr_auto] gap-x-3"><span className="type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</span><span className="truncate">{r.merchant} · {r.mcc_name}</span><span className="tabular-nums">{won(r.total)}</span></li>)}</ul>
  }
  if (k === "policy") return c.policy ? <dl className="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-1 text-sm"><dt className="type-meta">계정</dt><dd>{c.policy.account}</dd><dt className="type-meta">Don'ts</dt><dd className="whitespace-pre-line">{c.policy.donts || "—"}</dd><dt className="type-meta">증빙</dt><dd>{c.policy.required_evidence || "—"}</dd></dl> : null
  return null
}

function Shared({ c }: { c: CaseBundle }) {
  const [open, setOpen] = useState<"history" | "precedents" | "voucher" | null>(null)
  const t = c.transaction
  const items: { k: "history" | "precedents" | "voucher"; label: string; n?: number }[] = [
    { k: "history", label: "이 사용자 이력", n: c.context.history.flagged_tx },
    ...(c.precedents.cases.length ? [{ k: "precedents" as const, label: "과거 징계 사례", n: c.precedents.cases.length }] : []),
    { k: "voucher", label: "전표 정보" },
  ]
  return (
    <div className="mt-5">
      <div className="flex flex-wrap gap-1">
        {items.map((i) => <Badge key={i.k} variant={open === i.k ? "default" : "outline"} className="cursor-pointer" onClick={() => setOpen(open === i.k ? null : i.k)}>{i.label}{i.n ? ` ${i.n}` : ""}</Badge>)}
      </div>
      {open === "history" && <div className="mt-3"><p className="mb-2 text-sm">과거 결제 {c.profile.amount.user.n}건 · 규칙에 걸림 {c.context.history.flagged_tx}회 · 위반 판정 {c.context.history.violations}회 · 아님 판정 {c.context.history.cleared}회</p><Suspense fallback={Fallback}><HistoryWeeks profile={c.profile} /></Suspense></div>}
      {open === "precedents" && <ul className="mt-3 flex flex-col gap-1.5 text-sm">{c.precedents.cases.map((p) => <li key={p.precedent_id}><span className="font-medium">{p.title}</span> <span className="type-meta">{p.source}</span></li>)}</ul>}
      {open === "voucher" && (
        <dl className="mt-3 grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="type-meta">전표</dt><dd className="tabular-nums">{String(t.sap_doc_no ?? "—")} · 첨부 {t.has_attachment ? "있음" : "없음"}</dd>
          <dt className="type-meta">계정</dt><dd>{t.account_policy}</dd>
          <dt className="type-meta">승인자</dt><dd>{String(t.approver ?? "—")}</dd>
          <dt className="type-meta">적요</dt><dd>{t.memo ? String(t.memo) : "—"}</dd>
          {c.score && <><dt className="type-meta">모델</dt><dd className="type-meta">{c.score.learned_name ?? "기준선"} {c.score.score_learned?.toFixed(2) ?? ""} · {c.score.top_features_learned.slice(0, 2).map((f) => f[2]).join(" · ")}</dd></>}
        </dl>
      )}
    </div>
  )
}
