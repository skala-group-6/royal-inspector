import { ReferenceLine, Scatter, ScatterChart, XAxis, YAxis, ZAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { won, mmdd } from "@/lib/format"
import type { CaseBundle } from "@/types"

/**
 * Detail view: this user's recent transactions as dots on one amount line (strip plot), this one in red, the peer group's
 * usual amount as a tick. "평소" shown as the actual transactions rather than a summary. Linear scale; dots jitter vertically a little so ties stay visible.
 */
const config = { amt: { label: "금액" } } satisfies ChartConfig

export function AmountDots({ c, className }: { c: CaseBundle; className?: string }) {
  const x = c.transaction.total
  const recent = c.context.recent_tx.filter((r) => r.total > 0)
  if (recent.length < 3) return <div className={className}><div className="type-meta">본인 최근 거래가 {recent.length}건뿐이라 점으로 그리기엔 적음</div></div>
  const pts = recent.map((r, i) => ({ amt: r.total, y: (i % 5) - 2, merchant: r.merchant, when: mmdd(r.tx_ts), rules: r.rules.length }))
  const peerMed = c.profile.amount.peer.p50
  const max = Math.max(x, peerMed ?? 0, ...pts.map((p) => p.amt)) * 1.08
  return (
    <div className={className}>
      <ChartContainer config={config} className="h-[88px] w-full aspect-auto">
        <ScatterChart margin={{ top: 14, right: 16, bottom: 0, left: 8 }}>
          <XAxis type="number" dataKey="amt" domain={[0, max]} tickFormatter={man} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} height={16} />
          <YAxis type="number" dataKey="y" domain={[-3, 3]} hide />
          <ZAxis range={[36, 36]} />
          {peerMed != null && <ReferenceLine x={peerMed} stroke="var(--muted-foreground)" strokeDasharray="3 3" label={{ value: `동료 평소 ${won(peerMed)}`, position: "top", fontSize: 10, fill: "var(--muted-foreground)" }} />}
          <Scatter data={pts} fill="var(--muted-foreground)" fillOpacity={0.55} isAnimationActive={false} />
          <Scatter data={[{ amt: x, y: 0 }]} fill="var(--destructive)" isAnimationActive={false} shape={(p: { cx?: number; cy?: number }) => <circle cx={p.cx} cy={p.cy} r={6} fill="var(--destructive)" stroke="var(--surface-card)" strokeWidth={2} />} />
          <ReferenceLine x={x} stroke="var(--destructive)" strokeOpacity={0.4} label={{ value: "이 건", position: "top", fontSize: 10, fill: "var(--destructive)" }} />
          <ChartTooltip cursor={false} content={({ payload }) => {
            const d = payload?.[0]?.payload as (typeof pts)[number] | undefined
            if (!d?.merchant) return null
            return <div className="rounded-lg bg-surface-card px-3 py-2 text-xs shadow-sm ring-1 ring-black/5"><div className="font-medium">{d.when} · {d.merchant}</div><div className="type-meta">{won(d.amt)}{d.rules ? ` · 규칙 ${d.rules}개 걸림` : ""}</div></div>
          }} />
        </ScatterChart>
      </ChartContainer>
      <div className="mt-1 flex gap-3 type-meta">
        <span className="inline-flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-muted-foreground/55" />본인 최근 {pts.length}건</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block size-2.5 rounded-full bg-destructive" />이 건</span>
      </div>
    </div>
  )
}
function man(v: number) { return v === 0 ? "0" : v >= 10000 ? `${Math.round(v / 10000)}만` : `${Math.round(v / 1000)}천` }
