// Dev-only: the /gallery design page still reads this snapshot. Every real screen reads the API (src/api).
import raw from "./data.json"
import type { MockData } from "@/types"
export const mock = raw as unknown as MockData
