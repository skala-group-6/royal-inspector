import type { CaseBundle, QueueSource } from "@/types"
import { won } from "@/mock"

/**
 * One-sentence conclusion for a case, composed from rule outputs only (numbers come straight from flags.evidence).
 * Client-side templates for now; the server will own this (roadmap step 6 "근거 서술") and the UI will just render it.
 * Order of leads = which rule best explains "what happened" to a reader; the full reason list follows underneath.
 */
const LEADS = ["R02", "R01", "R05", "R07", "R12", "R17", "R18", "R08", "R11", "R03", "R06", "R10", "R15", "R14", "R09", "R16", "R13", "R04", "R21"]

const hm = (t: unknown) => String(t ?? "").slice(0, 5)
const g = (ev: Record<string, unknown>, k: string) => ev[k] as string | number | undefined

export function conclusion(c: CaseBundle, source?: QueueSource): string {
  const t = c.transaction
  const amt = won(t.total); const mcc = t.mcc_name ?? t.merchant
  if (!c.evidences.length) {
    return source === "model" ? `걸린 규칙은 없지만 모델이 평소와 다르다고 본 ${mcc} ${amt} 결제입니다.`
      : source === "random" ? `무작위 표본입니다. ${mcc}에서 ${amt}을 결제했습니다.`
      : `걸린 규칙이 없습니다. ${mcc}에서 ${amt}을 결제했습니다.`
  }
  const vio = c.evidences.filter((e) => e.severity === "violation")
  const pool = vio.length ? vio : c.evidences
  const lead = [...pool].sort((a, b) => LEADS.indexOf(a.rule_id.slice(0, 3)) - LEADS.indexOf(b.rule_id.slice(0, 3)))[0]
  const ev = lead.evidence; const id = lead.rule_id.slice(0, 3)
  const T: Record<string, () => string> = {
    R02: () => `${String(g(ev, "leave_type") ?? "휴가").trim()} 등록일 ${hm(g(ev, "time"))}에 ${mcc}에서 ${amt}을 결제했습니다.`,
    R01: () => `휴일(${g(ev, "weekday") ?? ""})에 ${mcc}에서 ${amt}을 결제했습니다.`,
    R05: () => `주거지 인근(${g(ev, "merchant_sigungu")})의 ${mcc}에서 ${hm(g(ev, "time"))}에 ${amt}을 결제했습니다.`,
    R07: () => `${g(ev, "trip_type") ?? "출장"} 중 출장지 밖(${g(ev, "merchant_sido")})의 ${mcc}에서 ${amt}을 결제했습니다.`,
    R12: () => `사옥 입문 ${g(ev, "minutes_before_purchase")}분 뒤 ${g(ev, "merchant_sido")}에서 결제되어 카드 대여가 의심됩니다.`,
    R17: () => `자택방문교통비를 ${g(ev, "merchant_sido")} 지역 ${mcc}에 ${amt} 결제했습니다.`,
    R18: () => `승인자 주거지 인근(${g(ev, "approver_sigungu")})의 ${mcc}에서 ${amt}을 결제했습니다.`,
    R08: () => `제한 업종(${mcc})에서 ${amt}을 ${t.account_policy}로 결제했습니다.`,
    R11: () => `${mcc} 결제 ${amt}을 맞지 않는 계정(${t.account_policy})으로 처리했습니다.`,
    R03: () => `${t.merchant}에서 ${g(ev, "window_min")}분 안에 ${g(ev, "count_in_window")}건, 합계 ${won(Number(g(ev, "group_total")))}을 나눠 결제했습니다.`,
    R06: () => `같은 시각 두 지역에서 결제되어 동일인 사용으로 보기 어렵습니다.`,
    R10: () => `증빙이 필요한 ${mcc} ${amt} 결제에 첨부가 없습니다.`,
    R15: () => `출장 종료 ${g(ev, "days_before_end")}일 전에 복귀 교통편을 결제했습니다.`,
    R14: () => `${g(ev, "trip_type") ?? "출장"} 중 식사 ${amt}을 ${t.account_policy}로 결제했습니다.`,
    R09: () => `주유가 잦습니다. 같은 날 ${g(ev, "same_day_count") ?? 1}회, 14일 내 ${g(ev, "count_in_14d") ?? 1}회.`,
    R16: () => `동료 중앙값의 ${g(ev, "ratio")}배인 ${amt}을 ${mcc}에서 결제했습니다.`,
    R13: () => `개인 물품 구매가 의심되는 ${mcc} ${amt} 결제입니다.`,
    R04: () => `${mcc}에서 ${amt} 단위 금액으로 선결제한 것으로 보입니다.`,
    R21: () => `${mcc} ${amt} 결제인데 적요의 참석 인원이 금액과 맞지 않습니다.`,
  }
  const s = (T[id] ?? (() => `${lead.headline}.`))()
  const more = vio.length - (vio.includes(lead) ? 1 : 0)
  return more > 0 ? `${s} 위반 사유가 ${more}건 더 있습니다.` : s
}
