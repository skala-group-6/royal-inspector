import { ListGroup, ListItem, ListMeta } from "@/components/layout/list"
import { mock } from "@/mock"

/** Load/queue history for the 데이터 section. One period in mock; real list comes with the API. */
export function DataRuns() {
  const p = mock.period
  return (
    <>
      <ListMeta><span>적재·큐 이력</span></ListMeta>
      <ListGroup>
        <ListItem active>
          <div className="type-label">{p.period_from} ~ {p.period_to}</div>
          <div className="type-meta">큐 {mock.queue.length}건 · 규칙 {mock.rules.length}개</div>
        </ListItem>
      </ListGroup>
    </>
  )
}
