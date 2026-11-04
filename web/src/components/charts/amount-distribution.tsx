import { Bar, CartesianGrid, ComposedChart, ReferenceLine, Scatter, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { won } from "@/mock"
import type { Profile } from "@/types"

/**
 * Question 1: "평소와 얼마나 다른가?" Two rows (본인 / 동료): the p25–p75 band as a thin bar, p90 as a dot,
 * and this transaction as one vertical reference line across both rows. Numbers are always printed beside the plot
 * (docs/DESIGN.md §8): the picture is for speed, the text for precision. Log scale because amounts span 10³–10⁶.
 */
const config = { band: { label: "25–75%" }, p90: { label: "90%" } } satisfies ChartConfig
const MIN_N = 5

/** `peerPercentile`: exact point-in-time percentile from the feature table (context.peer.percentile_of_this) when available; else interpolated from quantiles. */
export function AmountDistribution({ profile, peerPercentile, className }: { profile: Profile; peerPercentile?: number | null; className?: string }) {
  const { this: x, user, peer } = profile.amount
  const rows = [
    { key: "user", name: "본인", q: user },
    { key: "peer", name: "동료", q: peer },
  ].filter((r) => r.q.n >= MIN_N && r.q.p25 != null)
  const ratio = user.p50 ? x / user.p50 : null
  const peerTop = peerPercentile != null ? Math.max(1, Math.round(100 - peerPercentile)) : peer.n ? pctAbove(x, peer) : null
  if (!rows.length) {
    return <div className={className}><div className="type-meta">본인 과거 거래 {user.n}건 · 동료 {peer.n}건 — 분포를 그리기엔 적음</div></div>
  }
  const data = rows.map((r) => ({ row: r.name, band: [r.q.p25!, r.q.p75!], p90: r.q.p90!, n: r.q.n, p50: r.q.p50! }))
  const lo = Math.min(x, ...data.map((d) => d.band[0])) / 1.6, hi = Math.max(x, ...data.map((d) => d.p90)) * 1.6
  return (
    <div className={className}>
      <div className="grid grid-cols-[1fr_auto] items-center gap-x-6">
        <ChartContainer config={config} className="h-[72px] w-full aspect-auto">
          <ComposedChart data={data} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 0 }} barCategoryGap={6}>
            <CartesianGrid horizontal={false} stroke="var(--surface-selected)" strokeWidth={1} />
            <XAxis type="number" scale="log" domain={[lo, hi]} tickFormatter={compact} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} height={16} ticks={logTicks(lo, hi)} />
            <YAxis type="category" dataKey="row" width={30} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
            <Bar dataKey="band" fill="var(--muted-foreground)" fillOpacity={0.35} barSize={10} radius={4} isAnimationActive={false} />
            <Scatter dataKey="p90" fill="var(--muted-foreground)" shape={(p: { cx?: number; cy?: number }) => <circle cx={p.cx} cy={p.cy} r={4} fill="var(--muted-foreground)" stroke="var(--surface-card)" strokeWidth={2} />} isAnimationActive={false} />
            <ReferenceLine x={x} stroke="var(--destructive)" strokeWidth={2} />
            <ChartTooltip cursor={false} content={({ payload }) => {
              const d = payload?.[0]?.payload as (typeof data)[number] | undefined
              if (!d) return null
              return <div className="rounded-lg bg-surface-card px-3 py-2 text-xs shadow-sm ring-1 ring-black/5"><div className="font-medium">{d.row} · 과거 {d.n}건</div><div className="type-meta">25% {won(d.band[0])} · 중앙값 {won(d.p50)} · 75% {won(d.band[1])} · 90% {won(d.p90)}</div></div>
            }} />
          </ComposedChart>
        </ChartContainer>
        <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 text-sm">
          <dt className="type-meta">이 건</dt><dd className="font-semibold tabular-nums">{won(x)}</dd>
          <dt className="type-meta">{user.n >= MIN_N ? "본인 중앙값" : "본인 과거"}</dt><dd className="tabular-nums">{user.n >= MIN_N && user.p50 != null ? `${won(user.p50)}${ratio ? ` · ×${ratio.toFixed(1)}` : ""}` : `${user.n}건 — 비교 보류`}</dd>
          <dt className="type-meta">동료 기준</dt><dd className="tabular-nums">{peer.p50 != null ? `${won(peer.p50)}${peerTop != null ? ` · 상위 ${peerTop}%` : ""}` : "—"}</dd>
        </dl>
      </div>
      <div className="mt-1 flex items-center gap-3 type-meta">
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-muted-foreground/35" />25–75% 구간</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-muted-foreground" />90%</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block h-3 w-0.5 bg-destructive" />이 건</span>
      </div>
    </div>
  )
}

function compact(v: number) { return v >= 1_000_000 ? `${(v / 1_000_000).toFixed(v % 1_000_000 ? 1 : 0)}M` : v >= 1000 ? `${Math.round(v / 1000)}K` : String(Math.round(v)) }
function logTicks(lo: number, hi: number) { const t: number[] = []; for (let p = 1; p <= 1e8; p *= 10) for (const m of [1, 2, 5]) { const v = m * p; if (v >= lo && v <= hi) t.push(v) } return t.length > 5 ? t.filter((_, i) => i % 2 === 0) : t }
/** Approximate "top N%" from quantiles: linear interpolation on the known points. */
function pctAbove(x: number, q: Profile["amount"]["peer"]) {
  const pts = [[q.p25, 25], [q.p50, 50], [q.p75, 75], [q.p90, 90]].filter((p): p is [number, number] => p[0] != null)
  if (!pts.length) return null
  if (x >= pts[pts.length - 1][0]) return Math.max(1, Math.round(100 - pts[pts.length - 1][1]))
  if (x <= pts[0][0]) return Math.min(99, Math.round(100 - pts[0][1]))
  for (let i = 1; i < pts.length; i++) if (x <= pts[i][0]) { const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; return Math.round(100 - (y0 + ((x - x0) / (x1 - x0)) * (y1 - y0))) }
  return null
}
