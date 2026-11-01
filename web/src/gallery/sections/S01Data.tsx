import { mock, won, mmdd, hhmm } from "@/mock"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const SRC: Record<string, string> = { rule: "규칙", model: "🧠 모델", random: "🎲 무작위" }
export function S01Data() {
  return (
    <div className="flex flex-col gap-3">
      <Table>
        <TableHeader><TableRow><TableHead>tx_id</TableHead><TableHead>출처</TableHead><TableHead>일시</TableHead><TableHead>사용자</TableHead><TableHead>가맹점</TableHead><TableHead>금액</TableHead><TableHead>규칙</TableHead><TableHead>근거 문장 수</TableHead><TableHead>선례</TableHead><TableHead>학습 점수</TableHead></TableRow></TableHeader>
        <TableBody>
          {mock.queue.map((r) => { const c = mock.cases[String(r.tx_id)]; return (
            <TableRow key={r.tx_id}>
              <TableCell className="font-mono text-xs">{r.tx_id}</TableCell>
              <TableCell><Badge variant="outline">{SRC[r.queue_source]}</Badge></TableCell>
              <TableCell>{mmdd(r.tx_ts)} {hhmm(r.tx_ts)}</TableCell>
              <TableCell>{r.emp_name}</TableCell>
              <TableCell>{r.merchant} <span className="text-muted-foreground">[{r.mcc_name}]</span></TableCell>
              <TableCell className="tabular-nums">{won(r.total)}</TableCell>
              <TableCell>{r.rules.map((x) => x.slice(0, 3)).join(" ") || "—"}</TableCell>
              <TableCell>{c.evidences.length}</TableCell>
              <TableCell>{c.precedents.cases.length}</TableCell>
              <TableCell className="tabular-nums">{c.score?.score_learned?.toFixed(2) ?? ""}</TableCell>
            </TableRow>) })}
        </TableBody>
      </Table>
      <p className="text-muted-foreground text-xs">기간 {mock.period.period_from} ~ {mock.period.period_to} · 큐 출처별: {mock.summary.map((s) => `${SRC[s.source]} ${s.n.toLocaleString()}건`).join(" · ")}</p>
    </div>
  )
}
