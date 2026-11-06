import { Bar, BarChart, LabelList, XAxis, YAxis, Cell } from "recharts"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import { won } from "@/lib/format"
import type { Profile } from "@/types"

/**
 * First-glance answer to "how unusual is the amount": three horizontal bars — this transaction, this user's usual amount
 * (median of prior transactions), the peer group's usual amount. Bar length is the ratio; the number sits at the end of each bar.
 * shadcn "Bar Chart – Horizontal + Label" pattern. Distribution width is deliberately left to the detail view (AmountDots).
 */
const config = { v: { label: "금액" } } satisfies ChartConfig
const MIN_N = 5

export function AmountBars({ profile, className }: { profile: Profile; className?: string }) {
  const { this: x, user, peer } = profile.amount
  const rows = [
    { k: "이 건", v: x, focal: true },
    user.n >= MIN_N && user.p50 != null ? { k: `본인 평소 · ${user.n}건`, v: user.p50, focal: false } : null,
    peer.n >= MIN_N && peer.p50 != null ? { k: `동료 평소 · ${peer.n}건`, v: peer.p50, focal: false } : null,
  ].filter((r): r is { k: string; v: number; focal: boolean } => r != null)
  if (rows.length < 2) return <div className={className}><div className="type-meta">비교할 과거 기록이 적음 (본인 {user.n}건 · 동료 {peer.n}건)</div></div>
  const max = Math.max(...rows.map((r) => r.v))
  return (
    <div className={className}>
      <ChartContainer config={config} className="w-full aspect-auto" style={{ height: rows.length * 28 + 4 }}>
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 0 }} barCategoryGap={6}>
          <XAxis type="number" domain={[0, max * 1.05]} hide />
          <YAxis type="category" dataKey="k" width={110} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <Bar dataKey="v" radius={4} barSize={14} isAnimationActive={false}>
            {rows.map((r) => <Cell key={r.k} fill={r.focal ? "var(--destructive)" : "var(--muted-foreground)"} fillOpacity={r.focal ? 1 : 0.45} />)}
            <LabelList dataKey="v" position="right" formatter={(v: number) => won(v)} className="fill-foreground" fontSize={11} />
          </Bar>
        </BarChart>
      </ChartContainer>
    </div>
  )
}
