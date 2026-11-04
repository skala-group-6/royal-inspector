import { Link, useParams } from "@tanstack/react-router"
import { Badge } from "@/components/ui/badge"
import { ListGroup, ListItem, ListMeta } from "@/components/layout/list"
import { mock } from "@/mock"

export function RuleList() {
  const { ruleId } = useParams({ strict: false }) as { ruleId?: string }
  return (
    <>
      <ListMeta><span>규칙 {mock.rules.length}개 · 카탈로그 v2</span></ListMeta>
      <ListGroup>
        {mock.rules.map((r) => (
          <ListItem key={r.rule_id} asChild active={ruleId === r.rule_id} className="flex items-center gap-2">
            <Link to="/rules/$ruleId" params={{ ruleId: r.rule_id }}>
              <span className="w-8 shrink-0 font-mono type-meta">{r.rule_id.slice(0, 3)}</span>
              <span className="flex-1 truncate type-label">{r.name}</span>
              <Badge variant={r.tier === "violation" ? "destructive" : "outline"} className="h-4 px-1.5 text-[10px]">{r.tier === "violation" ? "위반" : "참고"}</Badge>
            </Link>
          </ListItem>
        ))}
      </ListGroup>
    </>
  )
}
