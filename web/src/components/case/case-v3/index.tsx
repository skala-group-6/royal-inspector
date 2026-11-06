/**
 * Case panel v3 — five layers, each a small component the page composes in order (docs/REVIEW_SCREEN.md "케이스 패널 v3").
 *   <Case.Conclusion>  what is suspected, how much        (always)
 *   <Case.Context>     the situation: that day or the amount (chosen by the strongest rule; null when the rule needs none)
 *   <Case.Findings>    one line per rule: observed | baseline
 *   <Case.Basis>       policy line + documents to check outside the system + precedents
 *   <Case.SecondOpinion> the model agrees or not, two reasons
 *   <Case.More>        shared, folded: user history, voucher
 *   <Case.Verdict>     three buttons; the current verdict is the pressed one
 * Parts take slices of CaseBundle and nothing else. What goes into a layer for a given rule comes from the pack (src/pack).
 */
export { Conclusion } from "./conclusion"
export { Context } from "./context"
export { Findings } from "./findings"
export { Basis } from "./basis"
export { SecondOpinion } from "./second-opinion"
export { More } from "./more"
export { Verdict } from "./verdict"
export { CasePanelV3 } from "./panel"
