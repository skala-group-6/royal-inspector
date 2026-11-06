import { Outlet, useParams } from "@tanstack/react-router"
import { Badge } from "@/components/ui/badge"
import { useRules } from "@/api/queries"

export function RulesLayout() {
  return <Outlet />
}

export function RulesEmpty() {
  return <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">왼쪽 목록에서 규칙을 선택하세요.</div>
}

export function RuleDetail() {
  const { ruleId } = useParams({ from: "/rules/$ruleId" })
  const { data: rules } = useRules()
  const r = rules?.find((x) => x.rule_id === ruleId)
  if (!rules) return null
  if (!r) return <div className="p-6 text-sm text-muted-foreground">해당 규칙이 없습니다. ({ruleId})</div>
  return (
    <div className="p-6 md:p-8">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold">{r.name}</h2>
        <Badge variant={r.tier === "violation" ? "destructive" : "outline"}>{r.tier === "violation" ? "위반 가능" : "참고"}</Badge>
        <span className="font-mono text-xs text-muted-foreground">{r.rule_id}</span>
      </div>
      <dl className="mt-6 grid max-w-2xl grid-cols-[6rem_1fr] gap-x-4 gap-y-3 text-sm">
        <dt className="text-muted-foreground">설명</dt><dd>{r.explain}</dd>
        <dt className="text-muted-foreground">근거 규정</dt><dd>{r.policy_ref}</dd>
      </dl>
      <p className="mt-6 text-sm text-muted-foreground">임계치 편집 · 확정 비율 · 백테스트는 다음 단계에서 채워집니다.</p>
    </div>
  )
}
