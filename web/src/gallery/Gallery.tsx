import type { ReactNode } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { sections } from "./sections"

export function Gallery() {
  return (
    <div className="mx-auto max-w-[1400px] px-6 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">검토 화면 갤러리</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          조각을 번호순으로 쌓는다. 데이터는 실제 DB에서 뽑은 거래 6건(마스킹), 모양은 서비스 함수 출력 그대로. 완성된 조각은 그대로 검토 화면으로 조립한다.
        </p>
      </header>
      <div className="flex flex-col gap-10">
        {sections.map((s) => (
          <Section key={s.id} id={s.id} title={s.title} description={s.description} status={s.status}>
            <s.component />
          </Section>
        ))}
      </div>
    </div>
  )
}

function Section({ id, title, description, status, children }: { id: string; title: string; description: string; status: "done" | "wip" | "todo"; children: ReactNode }) {
  return (
    <Card id={id} className="scroll-mt-6">
      <CardHeader>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="font-mono">{id}</Badge>
          <CardTitle className="text-base">{title}</CardTitle>
          <Badge variant={status === "done" ? "default" : status === "wip" ? "secondary" : "outline"}>{status === "done" ? "완료" : status === "wip" ? "진행" : "예정"}</Badge>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
