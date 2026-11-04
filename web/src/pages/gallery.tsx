import type { CSSProperties } from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { CheckListIcon, Database01Icon, Layers01Icon, ChartHistogramIcon, ShieldKeyIcon, SidebarLeftIcon } from "@hugeicons/core-free-icons"
import { Badge } from "@/components/ui/badge"
import { mock, mmdd, hhmm } from "@/mock"

/**
 * Design decision page (dev only, not in the rail): surface layers without lines.
 * Each preview sets the five candidate surface tokens inline so nothing global changes until a variant is chosen.
 */
type Surfaces = { base: string; card: string; panel: string; hover: string; selected: string }
type Variant = { key: string; title: string; note: string; dark: boolean; lines: boolean; s: Surfaces }

const L = (l: number) => `oklch(${l} 0.004 220)`
const VARIANTS: Variant[] = [
  { key: "now", title: "현재 · 라이트", note: "바탕과 카드 밝기 차이 1.3%. 구분을 선이 대신함", dark: false, lines: true,
    s: { base: L(0.987), card: L(1), panel: L(1), hover: L(0.963), selected: L(0.963) } },
  { key: "light", title: "제안 · 라이트", note: "바탕을 한 단계 어둡게, 패널은 중간, 선 없음", dark: false, lines: false,
    s: { base: L(0.955), card: L(1), panel: L(0.982), hover: L(0.962), selected: L(0.94) } },
  { key: "darkA", title: "다크 A · 카드가 깊게 (추천)", note: "카드 = 기본 배경. 라이트와 같은 규칙: 바탕이 카드에서 한 단계 멀다", dark: true, lines: false,
    s: { base: L(0.218), card: L(0.148), panel: L(0.178), hover: L(0.215), selected: L(0.255) } },
  { key: "darkB", title: "다크 B · 카드가 떠오름", note: "카드를 바탕보다 밝게. 라이트와 방향이 반대", dark: true, lines: false,
    s: { base: L(0.148), card: L(0.218), panel: L(0.195), hover: L(0.25), selected: L(0.285) } },
]

const RAIL = [ShieldKeyIcon, CheckListIcon, Database01Icon, Layers01Icon, ChartHistogramIcon]

function MiniShell({ v }: { v: Variant }) {
  const vars = { "--sb": v.s.base, "--sc": v.s.card, "--sp": v.s.panel, "--sh": v.s.hover, "--ss": v.s.selected } as CSSProperties
  const line = v.lines ? "border-border" : "border-transparent"
  const rows = mock.queue.slice(0, 5)
  return (
    <div className={v.dark ? "dark" : "light"}>
      <div style={vars} className="flex h-[340px] overflow-hidden rounded-xl bg-(--sb) text-foreground ring-1 ring-black/5">
        {/* rail */}
        <div className={`flex w-12 shrink-0 flex-col items-center gap-3 border-r py-3 ${line}`}>
          {RAIL.map((ic, i) => (
            <div key={i} className={`flex size-8 items-center justify-center rounded-lg ${i === 0 ? "bg-primary text-primary-foreground" : i === 1 ? "bg-(--sh)" : "text-muted-foreground"}`}>
              <HugeiconsIcon icon={ic} strokeWidth={2} className="size-4" />
            </div>
          ))}
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          {/* header band */}
          <div className="flex h-10 shrink-0 items-center gap-3 px-3 text-sm">
            <HugeiconsIcon icon={SidebarLeftIcon} strokeWidth={2} className="size-4 text-muted-foreground" />
            {v.lines && <div className="h-4 w-px bg-border" />}
            <span className="font-medium">검토</span>
          </div>
          {/* card */}
          <div className="mr-2 mb-2 ml-2 flex min-h-0 flex-1 overflow-hidden rounded-2xl bg-(--sc) shadow-sm">
            <div className={`flex w-56 shrink-0 flex-col border-r bg-(--sp) ${line}`}>
              <div className={`border-b px-3 pt-3 pb-2 ${line}`}>
                <div className="text-sm font-semibold">검토</div>
              </div>
              <div className={`flex justify-between border-b px-3 py-1.5 text-[11px] text-muted-foreground ${line}`}>
                <span>2025-03 큐 · 6건</span><span>미검토 5</span>
              </div>
              <div className={v.lines ? "" : "flex flex-col gap-0.5 p-1.5"}>
                {rows.map((r, i) => {
                  const sel = i === 0, hov = i === 2
                  const bg = sel ? "bg-(--ss)" : hov ? "bg-(--sh)" : ""
                  const shape = v.lines ? `border-b ${line} ${sel ? "shadow-[inset_3px_0_0_var(--foreground)]" : ""}` : "rounded-lg"
                  return (
                    <div key={r.tx_id} className={`grid grid-cols-[1fr_auto] gap-x-2 px-2.5 py-1.5 text-xs ${bg} ${shape}`}>
                      <span className="truncate font-medium">{r.emp_name} · {r.dept}</span>
                      <span className="text-right font-medium tabular-nums">{Math.round(r.total).toLocaleString("ko-KR")}</span>
                      <span className="truncate text-[11px] text-muted-foreground">{mmdd(r.tx_ts)} {hhmm(r.tx_ts)} · {r.merchant}</span>
                      <span className="flex justify-end gap-1">
                        {r.queue_source === "model" ? <Badge variant="outline" className="h-4 px-1 text-[9px]">모델 추천</Badge>
                          : <Badge variant="destructive" className="h-4 px-1 text-[9px]">위반 {Math.max(1, r.n_rules - 1)}</Badge>}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
            <div className="min-w-0 flex-1 p-4">
              <div className="text-[11px] text-muted-foreground">윤*송 · CL-GLNQJ2 · 팀원</div>
              <div className="mt-0.5 text-sm font-semibold">590,000원 · 미르노래연습장</div>
              <div className="mt-3 text-base font-bold leading-snug">연차 등록일 밤에 노래연습장에서 59만 원을 결제했습니다.</div>
              <div className="mt-3 flex flex-col gap-1.5">
                {["휴가(연차 종일) 등록일에 사용", "제한 업종 · 노래연습장", "의욕관리비 계정 불일치"].map((t) => (
                  <div key={t} className="flex items-center gap-2 rounded-lg bg-(--sp) px-2.5 py-1.5 text-xs">
                    <span className="font-semibold text-destructive">위반</span><span>{t}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Swatches({ s }: { s: Surfaces }) {
  return (
    <div className="mt-2 flex gap-3 text-[11px] text-muted-foreground">
      {(Object.entries(s) as [keyof Surfaces, string][]).map(([k, c]) => (
        <span key={k} className="flex items-center gap-1">
          <span className="size-3 rounded-sm ring-1 ring-black/10" style={{ background: c }} />
          {k} {c.match(/oklch\(([\d.]+)/)?.[1]}
        </span>
      ))}
    </div>
  )
}

export function GalleryPage() {
  return (
    <div className="p-6">
      <h2 className="text-base font-semibold">면의 층 비교 — 선 없이 구분</h2>
      <p className="mt-1 text-sm text-muted-foreground">선택 행은 첫 줄, 호버 상태는 셋째 줄. 근거 목록은 패널과 같은 보조 면을 씁니다.</p>
      <div className="mt-6 grid grid-cols-1 gap-8 xl:grid-cols-2">
        {VARIANTS.map((v) => (
          <section key={v.key}>
            <div className="mb-2 flex items-baseline gap-2">
              <span className="text-sm font-semibold">{v.title}</span>
              <span className="text-xs text-muted-foreground">{v.note}</span>
            </div>
            <MiniShell v={v} />
            <Swatches s={v.s} />
          </section>
        ))}
      </div>
    </div>
  )
}
