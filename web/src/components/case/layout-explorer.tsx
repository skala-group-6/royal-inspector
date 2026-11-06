import { lazy, Suspense, useEffect, useState } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft01Icon, ArrowRight01Icon } from "@hugeicons/core-free-icons"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { ListGroup, ListItem, ListMeta } from "@/components/layout/list"
import { Conclusion, Context, Findings, Basis, SecondOpinion, More, Verdict } from "@/components/case/case-v3"
import { humanLine, strongestRule } from "@/pack/corp_card"
import { won, hhmm, mmdd } from "@/lib/format"
import type { CaseBundle, QueueRow } from "@/types"

const DayTimeline = lazy(() => import("@/components/charts/day-timeline").then((m) => ({ default: m.DayTimeline })))
const Fallback = <div className="h-16 animate-pulse rounded-lg bg-surface-panel" />

/**
 * Layout explorer (gallery): the same five parts arranged four ways, inside a mini shell (list + panel) so list changes show too.
 *   A 두 칸        text left (conclusion → findings → basis → more), picture right (context → second opinion)
 *   B 고정 머리    conclusion and verdict pinned, only the middle scrolls
 *   C 이야기 순서  the day's timeline first with the rule hits pinned to it, then the sentence and the findings
 *   D 목록 확장    the list row carries the sentence + count; the panel starts at the context
 * ← → or the buttons switch. Nothing here is wired to the API; it reads the mock snapshot.
 */
export const LAYOUTS = [
  { key: "A1", title: "한 칸", note: "결론 → 그림(맥락) → 규칙 → 근거 → 모델. 한 칸, 위에서 아래로" },
  { key: "A", title: "두 칸", note: "글은 왼쪽, 그림은 오른쪽. 넓은 화면에서 스크롤 없이 한눈에" },
  { key: "B", title: "고정 머리", note: "결론과 판정 바를 고정, 가운데만 스크롤. 어디를 보든 무엇을 판정 중인지 보임" },
  { key: "C", title: "이야기 순서", note: "그날 동선을 맨 위에, 그 위에 규칙 적중을 핀으로. 장소·시간형 위반에 강함" },
  { key: "D", title: "목록 확장", note: "목록 행에 결론 문장과 위반 수. 패널은 맥락부터. 명백한 '아님'은 목록에서 거름" },
] as const
type Key = (typeof LAYOUTS)[number]["key"]

export function LayoutExplorer({ rows, cases }: { rows: QueueRow[]; cases: Record<string, CaseBundle> }) {
  const [i, setI] = useState(0)
  const [sel, setSel] = useState(rows[0]?.tx_id)
  const go = (d: number) => setI((x) => (x + d + LAYOUTS.length) % LAYOUTS.length)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName)) return; if (e.key === "ArrowRight") go(1); if (e.key === "ArrowLeft") go(-1) }
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey)
  }, [])
  const L = LAYOUTS[i]; const c = sel ? cases[sel] : undefined; const row = rows.find((r) => r.tx_id === sel)
  return (
    <section className="mb-12">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold">배치 탐색 — {L.key}. {L.title}</h2>
        <span className="text-sm text-muted-foreground">{L.note}</span>
        <span className="ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon-sm" onClick={() => go(-1)} aria-label="이전 배치"><HugeiconsIcon icon={ArrowLeft01Icon} strokeWidth={2} /></Button>
          <span className="type-meta tabular-nums">{i + 1}/{LAYOUTS.length}</span>
          <Button variant="ghost" size="icon-sm" onClick={() => go(1)} aria-label="다음 배치"><HugeiconsIcon icon={ArrowRight01Icon} strokeWidth={2} /></Button>
          <Kbd>←</Kbd><Kbd>→</Kbd>
        </span>
      </div>
      <div className="mt-3 flex h-[820px] overflow-hidden rounded-2xl bg-surface-card shadow-sm">
        <aside className="flex w-80 shrink-0 flex-col overflow-auto bg-surface-panel">
          <MiniList rows={rows} cases={cases} sel={sel} onSel={setSel} expanded={L.key === "D"} />
        </aside>
        <div className="min-w-0 flex-1">{c && <Panel k={L.key} c={c} row={row} />}</div>
      </div>
    </section>
  )
}

function MiniList({ rows, cases, sel, onSel, expanded }: { rows: QueueRow[]; cases: Record<string, CaseBundle>; sel?: string; onSel: (t: string) => void; expanded: boolean }) {
  return (
    <>
      <ListMeta><span>2025-03 큐 · {rows.length}건</span><span>미검토 {rows.filter((r) => r.review_status === "unreviewed").length}</span></ListMeta>
      <ListGroup>
        {rows.map((r) => {
          const c = cases[r.tx_id]; const vio = c?.evidences.filter((e) => e.severity === "violation").length ?? 0
          const line = c ? humanLine(c, r.queue_source).head : ""
          return (
            <ListItem key={r.tx_id} active={sel === r.tx_id} onClick={() => onSel(r.tx_id)} className={`grid cursor-pointer grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 ${expanded ? "py-2.5" : ""}`}>
              {expanded ? (
                <>
                  <span className="truncate type-label">{line || "걸린 규칙 없음"}</span>
                  <span className="text-right type-value">{Math.round(r.total).toLocaleString("ko-KR")}</span>
                  <span className="truncate type-meta">{r.emp_name} · {r.dept} · {mmdd(r.tx_ts)} {hhmm(r.tx_ts)} · {r.merchant}</span>
                  <span className="flex justify-end gap-1">{vio > 0 ? <Badge variant="destructive" className="h-4 px-1.5 text-[10px]">위반 {vio}</Badge> : <Badge variant="outline" className="h-4 px-1.5 text-[10px]">{r.queue_source === "model" ? "모델 추천" : r.queue_source === "random" ? "무작위" : "주의"}</Badge>}</span>
                </>
              ) : (
                <>
                  <span className="truncate type-label">{r.emp_name} · {r.dept}</span>
                  <span className="text-right type-value">{Math.round(r.total).toLocaleString("ko-KR")}</span>
                  <span className="truncate type-meta">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)} · {r.merchant}</span>
                  <span className="flex justify-end gap-1">{vio > 0 && <Badge variant="destructive" className="h-4 px-1.5 text-[10px]">위반 {vio}</Badge>}</span>
                </>
              )}
            </ListItem>
          )
        })}
      </ListGroup>
    </>
  )
}

function Panel({ k, c, row }: { k: Key; c: CaseBundle; row?: QueueRow }) {
  const source = row?.queue_source
  if (k === "A1") return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto px-8 pt-7 pb-6">
        <Conclusion c={c} source={source} /><Context c={c} source={source} /><Findings c={c} /><Basis c={c} /><SecondOpinion c={c} /><More c={c} />
      </div>
      <Verdict current={c.reviews[0]?.decision} />
    </div>
  )
  if (k === "A") return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="grid min-h-0 flex-1 grid-cols-[3fr_2fr] gap-8 overflow-auto px-8 pt-7 pb-6">
        <div className="flex min-w-0 flex-col gap-5"><Conclusion c={c} source={source} /><Findings c={c} /><Basis c={c} /><More c={c} /></div>
        <div className="flex min-w-0 flex-col gap-4"><Context c={c} source={source} /><SecondOpinion c={c} /></div>
      </div>
      <Verdict current={c.reviews[0]?.decision} />
    </div>
  )
  if (k === "B") return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 bg-surface-card px-8 pt-7 pb-4 shadow-[0_8px_12px_-12px_rgba(0,0,0,.35)]"><Conclusion c={c} source={source} /></div>
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto px-8 pt-4 pb-6"><Context c={c} source={source} /><Findings c={c} /><Basis c={c} /><SecondOpinion c={c} /><More c={c} /></div>
      <Verdict current={c.reviews[0]?.decision} />
    </div>
  )
  if (k === "C") {
    const lead = strongestRule(c); const t = c.transaction
    const pins = c.evidences.map((e) => `${e.severity === "violation" ? "⚠" : "ⓘ"} ${e.rule_name}`)
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto px-8 pt-7 pb-6">
          <div className="rounded-lg bg-surface-panel px-4 py-3">
            <div className="flex items-baseline justify-between"><p className="text-sm font-medium">{mmdd(t.tx_ts)} 그날 동선</p><p className="type-meta">{hhmm(t.tx_ts)} · {t.merchant} · {won(t.total)}</p></div>
            {c.timeline.length ? <Suspense fallback={Fallback}><DayTimeline c={c} /></Suspense> : <p className="mt-2 type-meta">그날 다른 결제·출입 기록 없음</p>}
            {pins.length > 0 && <p className="mt-2 text-sm"><span className="type-meta">{hhmm(t.tx_ts)} 이 결제에 걸린 것 · </span>{pins.join(" · ")}</p>}
          </div>
          <Conclusion c={c} source={source} />
          {lead && <Findings c={c} />}
          <Basis c={c} /><SecondOpinion c={c} /><More c={c} />
        </div>
        <Verdict current={c.reviews[0]?.decision} />
      </div>
    )
  }
  // D: the list already said what it is; the panel starts at the context, with a one-line strip for amount + count
  const vio = c.evidences.filter((e) => e.severity === "violation").length
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto px-8 pt-6 pb-6">
        <div className="flex items-center gap-3"><span className="text-xl font-semibold tabular-nums">{won(c.transaction.total)}</span>{vio > 0 && <Badge variant="destructive">위반 {vio}</Badge>}<span className="type-meta">{c.transaction.emp_name} · {c.transaction.dept} · {mmdd(c.transaction.tx_ts)} {hhmm(c.transaction.tx_ts)} · {c.transaction.merchant}</span></div>
        <Context c={c} source={source} /><Findings c={c} /><Basis c={c} /><SecondOpinion c={c} /><More c={c} />
      </div>
      <Verdict current={c.reviews[0]?.decision} />
    </div>
  )
}
