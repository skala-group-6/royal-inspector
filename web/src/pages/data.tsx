import { SiteHeader } from "@/components/site-header"

export function DataPage() {
  return (
    <>
      <SiteHeader title="데이터" />
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">업로드 · 열 매핑 · 적재 이력 (다음 단계)</div>
    </>
  )
}
