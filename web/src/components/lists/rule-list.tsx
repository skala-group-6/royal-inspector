import { Link, useParams } from "@tanstack/react-router"
import { Badge } from "@/components/ui/badge"
import { mock } from "@/mock"

export function RuleList() {
  const { ruleId } = useParams({ strict: false }) as { ruleId?: string }
  return (
    <div className="flex flex-col">
      <div className="border-b px-4 py-2 text-xs text-muted-foreground">규칙 {mock.rules.length}개 · 카탈로그 v2</div>
      {mock.rules.map((r) => (
        <Link
          key={r.rule_id}
          to="/rules/$ruleId"
          params={{ ruleId: r.rule_id }}
          data-active={ruleId === r.rule_id || undefined}
          className="flex items-center gap-2 border-b px-4 py-2.5 text-sm hover:bg-sidebar-accent data-active:bg-sidebar-accent data-active:shadow-[inset_3px_0_0_var(--sidebar-foreground)]"
        >
          <span className="w-8 shrink-0 font-mono text-xs text-muted-foreground">{r.rule_id.slice(0, 3)}</span>
          <span className="flex-1 truncate font-medium">{r.name}</span>
          <Badge variant={r.tier === "violation" ? "destructive" : "outline"} className="h-4 px-1.5 text-[10px]">{r.tier === "violation" ? "위반" : "참고"}</Badge>
        </Link>
      ))}
    </div>
  )
}
