"""Response/request schemas. Mirror web/src/types.ts one-to-one; ids are strings. Changing a field here means changing types.ts."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

TxId = str
QueueSource = Literal["rule", "model", "random"]
Decision = Literal["violation", "ok", "hold"]
ReviewStatus = Literal["unreviewed", "violation", "ok", "hold"]

class QueueRow(BaseModel):
    queue_source: QueueSource; selection_prob: float; rank_in_source: int | None
    tx_id: TxId; tx_ts: str; emp_id: int | None; emp_name: str | None; dept: str | None; rank: str | None
    account_policy: str | None; merchant: str | None; mcc_name: str | None; total: float; is_synthetic: bool
    rules: list[str]; n_rules: int; sev: int; review_status: ReviewStatus
    score: float | None = None; score_learned: float | None = None

class FlagRow(QueueRow):
    queue_source: QueueSource | None = None; selection_prob: float | None = None; rank_in_source: int | None = None

class RelatedTx(BaseModel):
    tx_id: TxId; tx_ts: str; emp_name: str | None; account_policy: str | None; merchant: str | None; mcc_name: str | None; total: float

class Evidence(BaseModel):
    rule_id: str; rule_name: str; rule_class: str; severity: Literal["violation", "advisory"]; cluster: str
    fact: str; brief_value: str; brief_verdict: str
    evidence: dict[str, Any]; evidence_text: str; headline: str; detail: str; citation: str; explain: str
    related_tx: list[RelatedTx]; rule_version: int

class Peer(BaseModel):
    account_policy: str | None; mcc_name: str | None; n: int; median: float | None; p90: float | None; percentile_of_this: float | None
    point_in_time: bool | None = None; as_of: str | None = None

class RecentTx(BaseModel):
    tx_id: TxId; tx_ts: str; account_policy: str | None; merchant: str | None; mcc_name: str | None; merchant_addr: str | None; total: float; rules: list[str]

class Access(BaseModel): access_ts: str; gate: str | None; event: str | None; direction: str | None

class Context(BaseModel):
    recent_tx: list[RecentTx]; peer: Peer | None; access_same_day: list[Access]
    trip: dict[str, Any] | None; leave: dict[str, Any] | None; holiday: bool
    history: dict[str, int]

class TimelineRow(BaseModel): ts: str; kind: str; what: str; place: str | None; amount: float | None; focal: bool

class Precedent(BaseModel):
    precedent_id: str; kind: Literal["case", "review"]; title: str; summary: str | None; cues: list[str]; outcome: str | None; source: str | None
    score: float; overlap: list[str]; only_in_precedent: list[str]; only_in_tx: list[str]

class Precedents(BaseModel): cases: list[Precedent]; reviews: list[Precedent]; summary: dict[str, int]

class Score(BaseModel):
    score: float | None; model_version: str | None; rank_pct: float | None = None; top_features: list[list[Any]]
    score_learned: float | None; learned_name: str | None; top_features_learned: list[list[Any]]; disclaimer: str

class Policy(BaseModel): account: str; description: str | None; dos: str | None; donts: str | None; required_evidence: str | None

class Review(BaseModel):
    review_id: str; rule_id: str | None; decision: Decision; reason_code: str | None; memo: str | None; reviewer: str; created_at: str; superseded: bool

class Quantiles(BaseModel): n: int; p25: float | None; p50: float | None; p75: float | None; p90: float | None
class Week(BaseModel): week_start: str; flagged: int; violations: int
class Profile(BaseModel): amount: dict[str, Any]; weekly: list[Week]

class CaseBundle(BaseModel):
    tx_id: TxId; transaction: dict[str, Any]; evidences: list[Evidence]; context: Context; timeline: list[TimelineRow]
    precedents: Precedents; score: Score | None; policy: Policy | None; reviews: list[Review]; profile: Profile

class Rule(BaseModel):
    rule_id: str; name: str; tier: Literal["violation", "advisory"]; cluster: str; rule_class: str; data_ready: str | None = None
    params: str | None = None; explain: str; policy_ref: str

class ReasonCode(BaseModel): code: str; label: str

class SummaryRow(BaseModel):
    source: QueueSource; n: int; reviewed: int; violation: int; ok: int; hold: int; hit_rate_pct: float | None; selection_prob: float; est_missed: float | None

class QueuePeriod(BaseModel): period_from: str; period_to: str; n: int; built_at: str

class ReviewIn(BaseModel):
    """A human verdict. rule_id null = transaction-level (one review per flagged rule; unflagged rows get a single rule-less review)."""
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    reason_code: str | None = None
    memo: str | None = Field(default=None, max_length=2000)
    rule_id: str | None = None

class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: str = Field(max_length=64)
    payload: dict[str, Any] | None = None

class NextOut(BaseModel): tx_id: TxId | None
