import { SiteHeader } from "@/components/site-header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
export function SummaryPage() {
  return (<><SiteHeader title="요약" />
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      <Card>
        <CardHeader><CardTitle>요약 화면은 준비 중입니다</CardTitle>
          <CardDescription>출처별 적중, 미처리율, 규칙별 확정 비율, 사용자 누적 의심도가 여기에 표시됩니다 (계획 4단계).</CardDescription></CardHeader>
        <CardContent className="text-sm text-muted-foreground">데이터 연결(계획 3단계) 이후 채워집니다.</CardContent>
      </Card>
    </div></>)
}
