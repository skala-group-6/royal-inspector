import raw from "./data.json"
import type { MockData } from "@/types"
export const mock = raw as unknown as MockData
export const RULE_NAME: Record<string, string> = Object.fromEntries(mock.rules.map((r) => [r.rule_id, r.name]))
export const won = (v: number | null | undefined) => (v == null ? "" : `${Math.round(v).toLocaleString("ko-KR")}원`)
export const hhmm = (iso: string) => iso.slice(11, 16)
export const mmdd = (iso: string) => iso.slice(5, 10)
