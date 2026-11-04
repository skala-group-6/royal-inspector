import { CartesianGrid, ReferenceArea, Scatter, ScatterChart, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { won, hhmm } from "@/mock"
import type { CaseBundle } from "@/types"

/**
 * Question 2: "그날 이 사람은 어디서 뭘 했나?" One day on a 0–24h axis. Rows: 출입 (in→out intervals as blocks) and 카드 (payments as dots,
 * this one emphasized). Work hours are a faint band; leave / trip / holiday are stated in text above the plot (not color-only).
 */
const config = { card: { label: "결제" }, access: { label: "출입" } } satisfies ChartConfig
const ROW = { access: 1, card: 0 } as const

export function DayTimeline({ c, className }: { c: CaseBundle; className?: string }) {
  const t = c.transaction
  const day = t.tx_ts.slice(0, 10)
  const hourOf = (iso: string) => { const [h, m, s] = iso.slice(11, 19).split(":").map(Number); return h + m / 60 + (s || 0) / 3600 }
  const cards = c.timeline.filter((x) => x.kind === "카드").map((x) => ({ x: hourOf(x.ts), y: ROW.card, label: x.what, amount: x.amount, ts: x.ts, focal: x.focal }))
  const access = c.context.access_same_day
  const ins = access.filter((a) => a.direction === "in").map((a) => hourOf(a.access_ts))
  const outs = access.filter((a) => a.direction === "out").map((a) => hourOf(a.access_ts))
  const intervals: [number, number][] = []
  if (ins.length) { const sortedIn = [...ins].sort((a, b) => a - b), sortedOut = [...outs].sort((a, b) => a - b); const first = sortedIn[0], last = sortedOut.length ? sortedOut[sortedOut.length - 1] : null; intervals.push([first, last != null && last > first ? last : Math.min(24, first + 0.25)]) }
  const accessDots = access.map((a) => ({ x: hourOf(a.access_ts), y: ROW.access, label: `${a.gate} · ${a.event}`, ts: a.access_ts }))
  const [ws, we] = [parseHour(t.work_start as string | null), parseHour(t.work_end as string | null)]
  const flags = [t.is_holiday ? "휴일" : null, c.context.leave ? `휴가 · ${c.context.leave.type.trim()} ${c.context.leave.hours}h` : null, c.context.trip ? `${c.context.trip.type} ${c.context.trip.start.slice(5, 10)}~${c.context.trip.end.slice(5, 10)}` : null].filter(Boolean)
  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-x-3 type-meta">
        <span>{day} ({t.weekday as string})</span>
        {ws != null && we != null && <span>근무 {t.work_start as string}–{t.work_end as string}</span>}
        <span>{access.length ? `사옥 출입 ${access.length}회` : "사옥 출입 기록 없음"}</span>
        {flags.map((f) => <span key={f} className="font-medium text-foreground">{f}</span>)}
      </div>
      <ChartContainer config={config} className="mt-1 h-[92px] w-full aspect-auto">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical horizontal={false} stroke="var(--surface-selected)" strokeWidth={1} />
          <XAxis type="number" dataKey="x" domain={[0, 24]} ticks={[0, 3, 6, 9, 12, 15, 18, 21, 24]} tickFormatter={(v) => `${v}시`} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} height={16} />
          <YAxis type="number" dataKey="y" domain={[-0.5, 1.5]} ticks={[0, 1]} tickFormatter={(v) => (v === 1 ? "출입" : "결제")} width={30} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          {ws != null && we != null && <ReferenceArea x1={ws} x2={we} y1={-0.5} y2={1.5} fill="var(--muted-foreground)" fillOpacity={0.06} />}
          {intervals.map(([a, b], i) => <ReferenceArea key={i} x1={a} x2={b} y1={0.72} y2={1.28} fill="var(--muted-foreground)" fillOpacity={0.3} radius={4} />)}
          <Scatter data={accessDots} shape={(p: { cx?: number; cy?: number }) => <circle cx={p.cx} cy={p.cy} r={3} fill="var(--muted-foreground)" stroke="var(--surface-card)" strokeWidth={2} />} isAnimationActive={false} />
          <Scatter data={cards} shape={(p: { cx?: number; cy?: number; payload?: { focal: boolean } }) => p.payload?.focal
            ? <circle cx={p.cx} cy={p.cy} r={6} fill="var(--destructive)" stroke="var(--surface-card)" strokeWidth={2} />
            : <circle cx={p.cx} cy={p.cy} r={4} fill="var(--muted-foreground)" stroke="var(--surface-card)" strokeWidth={2} />} isAnimationActive={false} />
          <ChartTooltip cursor={false} content={({ payload }) => {
            const d = payload?.[0]?.payload as { label: string; ts: string; amount?: number | null; focal?: boolean } | undefined
            if (!d) return null
            return <div className="rounded-lg bg-surface-card px-3 py-2 text-xs shadow-sm ring-1 ring-black/5"><div className="font-medium">{hhmm(d.ts)} {d.amount != null ? won(d.amount) : ""}{d.focal ? " · 이 건" : ""}</div><div className="type-meta">{d.label}</div></div>
          }} />
        </ScatterChart>
      </ChartContainer>
      <div className="mt-1 flex items-center gap-3 type-meta">
        <span className="inline-flex items-center gap-1"><span className="inline-block size-2.5 rounded-full bg-destructive" />이 건</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-muted-foreground" />다른 결제</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-muted-foreground/30" />사옥 체류</span>
        {ws != null && <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-muted-foreground/10" />근무시간</span>}
      </div>
    </div>
  )
}

function parseHour(s: string | null | undefined) { if (!s) return null; const m = /^(\d{1,2}):(\d{2})/.exec(String(s)); return m ? Number(m[1]) + Number(m[2]) / 60 : null }
