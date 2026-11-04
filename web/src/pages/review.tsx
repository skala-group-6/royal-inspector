import { Outlet, useParams } from "@tanstack/react-router"
import { SiteHeader } from "@/components/site-header"
import { mock, won } from "@/mock"

export function ReviewLayout() {
  return (<><SiteHeader title="검토" /><Outlet /></>)
}

export function ReviewEmpty() {
  return <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">왼쪽 목록에서 건을 선택하세요.</div>
}

/** Case panel body comes in plan 2-③ (conclusion → reasons → collapsed sections → verdict bar). Here: title line only. */
export function ReviewCase() {
  const { txId } = useParams({ from: "/review/$txId" })
  const c = mock.cases[txId]
  if (!c) return <div className="p-6 text-sm text-muted-foreground">해당 건이 없습니다. (ID {txId})</div>
  const t = c.transaction
  return (
    <div className="p-6 md:p-8">
      <div className="text-sm text-muted-foreground">{t.emp_name} · {t.dept} · {t.rank ?? ""}</div>
      <h2 className="mt-1 text-base font-semibold">{won(t.total)} · {t.merchant} · {t.tx_ts.replace("T", " ").slice(0, 16)} · {t.account_policy}</h2>
      <p className="mt-6 text-sm text-muted-foreground">결론 · 근거 · 판정은 다음 단계에서 채워집니다.</p>
    </div>
  )
}
