/** TanStack Query hooks, one per API resource. Keys: ["periods"], ["queue", pf, pt], ["case", txId], ["rules"], ["reason-codes"], ["summary", pf, pt]. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, qs } from "@/api/client"
import type { CaseBundle, Decision, MockData, QueueRow, Review, TxId } from "@/types"

export interface Period { period_from: string; period_to: string; n: number; built_at: string }
export type Rule = MockData["rules"][number]
export type ReasonCode = MockData["reason_codes"][number]
export type SummaryRow = MockData["summary"][number]

/** Rows the list shows at once (queue order). The full queue is thousands of rows; filters and paging come with the simplified screen. */
export const QUEUE_PAGE = 500

export const usePeriods = () => useQuery({ queryKey: ["periods"], queryFn: () => api<Period[]>("/queues"), staleTime: 60_000 })
/** The period the screen works on: the most recent queue. */
export function useCurrentPeriod() { const q = usePeriods(); return { ...q, period: q.data?.[0] } }

export const useQueue = (pf?: string, pt?: string, params: Record<string, string | number | boolean | undefined> = {}) =>
  useQuery({ queryKey: ["queue", pf, pt, params], enabled: !!pf && !!pt, queryFn: () => api<QueueRow[]>(`/queues/${pf}/${pt}/items${qs({ page_size: QUEUE_PAGE, ...params })}`) })
export const useSummary = (pf?: string, pt?: string) =>
  useQuery({ queryKey: ["summary", pf, pt], enabled: !!pf && !!pt, queryFn: () => api<SummaryRow[]>(`/queues/${pf}/${pt}/summary`) })
export const useCase = (txId?: TxId) =>
  useQuery({ queryKey: ["case", txId], enabled: !!txId, queryFn: () => api<CaseBundle>(`/tx/${txId}/case`) })
export const useRules = () => useQuery({ queryKey: ["rules"], queryFn: () => api<Rule[]>("/rules"), staleTime: Infinity })
export const useReasonCodes = () => useQuery({ queryKey: ["reason-codes"], queryFn: () => api<ReasonCode[]>("/reason-codes"), staleTime: Infinity })

/** The one write a screen can make. On success the case and every queue list refresh, so the row's status badge updates. */
export function useReview(txId: TxId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { decision: Decision; reason_code?: string; memo?: string; rule_id?: string }) => api<Review[]>(`/tx/${txId}/review`, { method: "POST", json: v }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["case", txId] }); qc.invalidateQueries({ queryKey: ["queue"] }); qc.invalidateQueries({ queryKey: ["summary"] }) },
  })
}
export const logEvent = (event: string, payload?: Record<string, unknown>) => api<void>("/events", { method: "POST", json: { event, payload } }).catch(() => undefined)
