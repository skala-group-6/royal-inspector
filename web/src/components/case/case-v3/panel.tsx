import { Conclusion } from "./conclusion"
import { Context } from "./context"
import { Findings } from "./findings"
import { Basis } from "./basis"
import { SecondOpinion } from "./second-opinion"
import { More } from "./more"
import { Verdict } from "./verdict"
import type { CaseBundle, Decision, QueueSource } from "@/types"

/** The five layers in order, then the shared fold, then the verdict bar. This is the whole composition; pages use it or compose their own. */
export function CasePanelV3({ c, source, reasonCodes, saving, onVerdict }: { c: CaseBundle; source?: QueueSource; reasonCodes?: { code: string; label: string }[]; saving?: boolean; onVerdict?: (d: Decision, reason?: string, memo?: string) => void }) {
  return (
    <div data-slot="case-panel" className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto px-8 pt-7 pb-6">
        <Conclusion c={c} source={source} />
        <Context c={c} source={source} />
        <Findings c={c} />
        <Basis c={c} />
        <SecondOpinion c={c} />
        <More c={c} />
      </div>
      <Verdict current={c.reviews[0]?.decision} reasonCodes={reasonCodes} saving={saving} onVerdict={onVerdict} />
    </div>
  )
}
