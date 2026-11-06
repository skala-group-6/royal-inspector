import { ListGroup, ListItem, ListMeta } from "@/components/layout/list"
import { usePeriods, useRules } from "@/api/queries"

/** Queue history for the 데이터 section: one row per built period (GET /queues). */
export function DataRuns() {
  const { data: periods = [] } = usePeriods(); const { data: rules = [] } = useRules()
  return (
    <>
      <ListMeta><span>적재·큐 이력</span></ListMeta>
      <ListGroup>
        {periods.map((p, i) => (
          <ListItem key={`${p.period_from}~${p.period_to}`} active={i === 0}>
            <div className="type-label">{p.period_from} ~ {p.period_to}</div>
            <div className="type-meta">큐 {p.n}건 · 규칙 {rules.length}개 · {p.built_at.slice(0, 16).replace("T", " ")}</div>
          </ListItem>
        ))}
      </ListGroup>
    </>
  )
}
