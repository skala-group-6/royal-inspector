import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import type { Profile } from "@/types"

/**
 * Question 3: "처음인가, 반복인가?" 13 weeks before the transaction: flagged transactions per week, with confirmed violations as the
 * lower (status-colored) segment. A 2px surface stroke separates stacked segments and neighbors (the "gap", not a border).
 * Only the maximum week is direct-labeled; the tooltip and the legend carry the rest.
 */
const config = { violations: { label: "위반 확정" }, other: { label: "적중(미확정·아님)" } } satisfies ChartConfig

export function HistoryWeeks({ profile, className }: { profile: Profile; className?: string }) {
  const data = profile.weekly.map((w) => ({ week: w.week_start.slice(5, 10), violations: w.violations, other: Math.max(0, w.flagged - w.violations), flagged: w.flagged }))
  const total = data.reduce((s, d) => s + d.flagged, 0), vio = data.reduce((s, d) => s + d.violations, 0)
  const max = Math.max(0, ...data.map((d) => d.flagged)); const maxIdx = data.findIndex((d) => d.flagged === max)
  return (
    <div className={className}>
      <div className="flex items-baseline gap-3 text-sm">
        <span className="font-semibold tabular-nums">{total}건</span><span className="type-meta">최근 13주 적중</span>
        <span className="font-semibold tabular-nums">{vio}건</span><span className="type-meta">위반 확정</span>
        {!total && <span className="type-meta">— 이 기간엔 처음</span>}
      </div>
      <ChartContainer config={config} className="mt-1 h-[96px] w-full aspect-auto">
        <BarChart data={data} margin={{ top: 14, right: 4, bottom: 0, left: 0 }} barCategoryGap={3}>
          <CartesianGrid vertical={false} stroke="var(--surface-selected)" strokeWidth={1} />
          <XAxis dataKey="week" interval={3} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} height={16} />
          <YAxis allowDecimals={false} width={20} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <Bar dataKey="violations" stackId="w" fill="var(--destructive)" stroke="var(--surface-card)" strokeWidth={2} maxBarSize={24} isAnimationActive={false} />
          <Bar dataKey="other" stackId="w" fill="var(--muted-foreground)" fillOpacity={0.45} stroke="var(--surface-card)" strokeWidth={2} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false}>
            {data.map((_, i) => <Cell key={i} fillOpacity={i === data.length - 1 ? 0.7 : 0.45} />)}
            {max > 0 && <LabelList dataKey="flagged" position="top" fontSize={10} fill="var(--foreground)" formatter={(v: unknown, _n?: unknown, i?: number) => (i === maxIdx ? String(v) : "")} />}
          </Bar>
          <ChartTooltip cursor={{ fill: "var(--surface-hover)" }} content={({ payload, label }) => {
            const d = payload?.[0]?.payload as (typeof data)[number] | undefined
            if (!d) return null
            return <div className="rounded-lg bg-surface-card px-3 py-2 text-xs shadow-sm ring-1 ring-black/5"><div className="font-medium">{label} 주 · 적중 {d.flagged}건</div><div className="type-meta">위반 확정 {d.violations} · 기타 {d.other}</div></div>
          }} />
        </BarChart>
      </ChartContainer>
      <div className="mt-1 flex items-center gap-3 type-meta">
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-destructive" />위반 확정</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm bg-muted-foreground/45" />적중(미확정·아님)</span>
        <span>마지막 막대 = 이번 주(이 건 이전)</span>
      </div>
    </div>
  )
}
