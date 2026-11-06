import { Bar, ComposedChart, ReferenceArea, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, type ChartConfig } from "@/components/ui/chart"
import { won } from "@/lib/format"
import type { Profile } from "@/types"

/**
 * Bullet chart (Few): one measure against reference bands. The bar is this transaction; the bands are the peer group's
 * usual range (25–75%) and upper range (75–90%); the tick is this user's usual amount (median). Linear scale on purpose:
 * when the amount is far outside the bands they bunch up on the left, which is exactly "how far out" at a glance.
 * Band labels move under the axis when the bands are too narrow to hold them.
 */
const config = { v: { label: "이 건" } } satisfies ChartConfig
const MIN_N = 5

export function AmountBullet({ profile, className }: { profile: Profile; className?: string }) {
  const { this: x, user, peer } = profile.amount
  const hasPeer = peer.n >= MIN_N && peer.p25 != null && peer.p75 != null && peer.p90 != null
  const hasUser = user.n >= MIN_N && user.p50 != null
  if (!hasPeer && !hasUser) return <div className={className}><div className="type-meta">비교할 과거 기록이 적음 (본인 {user.n}건 · 동료 {peer.n}건)</div></div>
  const max = Math.max(x, hasPeer ? peer.p90! : 0, hasUser ? user.p50! : 0) * 1.12
  const narrow = hasPeer ? (peer.p90! - peer.p25!) / max < 0.22 : false   // bands too thin for labels inside
  return (
    <div className={className}>
      <ChartContainer config={config} className="h-[64px] w-full aspect-auto">
        <ComposedChart data={[{ k: "이 건", v: x }]} layout="vertical" margin={{ top: 14, right: 12, bottom: 0, left: 4 }}>
          <XAxis type="number" domain={[0, max]} ticks={ticks(max)} tickFormatter={man} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} height={16} />
          <YAxis type="category" dataKey="k" hide />
          {hasPeer && <ReferenceArea x1={peer.p25!} x2={peer.p75!} fill="var(--muted-foreground)" fillOpacity={0.22} ifOverflow="visible" label={narrow ? undefined : { value: "동료 보통", position: "insideTop", fontSize: 10, fill: "var(--muted-foreground)" }} />}
          {hasPeer && <ReferenceArea x1={peer.p75!} x2={peer.p90!} fill="var(--muted-foreground)" fillOpacity={0.4} ifOverflow="visible" label={narrow ? undefined : { value: "상위 10%", position: "insideTop", fontSize: 10, fill: "var(--muted-foreground)" }} />}
          {hasUser && <ReferenceLine x={user.p50!} stroke="var(--foreground)" strokeWidth={2} label={{ value: `평소 ${won(user.p50!)}`, position: "top", fontSize: 10, fill: "var(--foreground)" }} />}
          <Bar dataKey="v" barSize={8} fill="var(--destructive)" radius={4} isAnimationActive={false} />
        </ComposedChart>
      </ChartContainer>
      {hasPeer && narrow && (
        <div className="flex gap-3 type-meta">
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-muted-foreground/25" />동료 보통 {won(peer.p25!)}–{won(peer.p75!)}</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-muted-foreground/45" />상위 10% {won(peer.p90!)}</span>
        </div>
      )}
    </div>
  )
}

function man(v: number) { return v === 0 ? "0" : v >= 1_0000_0000 ? `${(v / 1_0000_0000).toFixed(1)}억` : v >= 10000 ? `${Math.round(v / 10000)}만` : `${Math.round(v / 1000)}천` }
function ticks(max: number) { const step = niceStep(max / 4); const t: number[] = []; for (let v = 0; v <= max; v += step) t.push(v); return t }
function niceStep(raw: number) { const p = 10 ** Math.floor(Math.log10(raw)); const m = raw / p; return (m >= 5 ? 5 : m >= 2 ? 2 : 1) * p }
