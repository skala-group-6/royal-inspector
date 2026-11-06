"""HTTP boundary for the review product. Every route calls one function in app/service.py and returns its result encoded
(api/encode.py: ids as strings) and validated (api/schemas.py: the contract shared with web/src/types.ts).
Who is acting comes from the X-Reviewer header (dev default until login exists); only POST /tx/{id}/review writes a verdict."""
from __future__ import annotations
import re, sys
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, APIRouter, Header, HTTPException, Query
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import service as s
from api.encode import clean
from api import schemas as S

app = FastAPI(title="royal-inspector", version="0.1", docs_url="/api/docs", openapi_url="/api/openapi.json")
r = APIRouter(prefix="/api")
_ID = re.compile(r"^-?\d{1,20}$")

def tx(tx_id: str) -> int:
    if not _ID.match(tx_id): raise HTTPException(400, "tx_id must be an integer string")
    v = int(tx_id)
    if not s.tx_exists(v): raise HTTPException(404, f"transaction {tx_id} not found")
    return v

def many(model, rows): return [model.model_validate(x) for x in clean(rows)]
def one(model, obj): return None if obj is None else model.model_validate(clean(obj))
def _list(v: str | None): return [x for x in v.split(",") if x] if v else None

@r.get("/health")
def health(): return {"ok": True, "tenant": s.one("select tenant()")}

# ---- lists
@r.get("/queues", response_model=list[S.QueuePeriod])
def queues(): return many(S.QueuePeriod, s.list_queue_periods())

@r.get("/queues/{pf}/{pt}/items", response_model=list[S.QueueRow])
def queue_items(pf: str, pt: str, sources: str | None = None, rule_ids: str | None = None, depts: str | None = None, min_total: float | None = None,
                review_status: str | None = None, sort: str = "source", page: int = 1, page_size: Annotated[int, Query(le=10000)] = 100, synthetic_only: bool | None = None):
    df = s.list_queue(pf, pt, _list(sources), _list(rule_ids), _list(depts), min_total, review_status, sort, page, page_size, synthetic_only)
    return many(S.QueueRow, df.drop(columns=["one"], errors="ignore"))

@r.get("/queues/{pf}/{pt}/summary", response_model=list[S.SummaryRow])
def queue_summary(pf: str, pt: str): return many(S.SummaryRow, s.get_queue_summary(pf, pt))

@r.get("/flags", response_model=list[S.FlagRow])
def flags(rule_ids: str | None = None, depts: str | None = None, date_from: str | None = None, date_to: str | None = None, min_total: float | None = None,
          review_status: str | None = None, sort: str = "total", page: int = 1, page_size: Annotated[int, Query(le=10000)] = 100, synthetic_only: bool | None = None):
    df = s.list_flags(_list(rule_ids), _list(depts), date_from, date_to, min_total, review_status, sort, page, page_size, synthetic_only)
    return many(S.FlagRow, df.drop(columns=["one"], errors="ignore"))

@r.get("/next", response_model=S.NextOut)
def next_unreviewed(after: str, pf: str | None = None, pt: str | None = None, sources: str | None = None, rule_ids: str | None = None, sort: str = "source"):
    nxt = s.next_unreviewed(tx(after), queue_period=(pf, pt) if pf and pt else None, sources=_list(sources), rule_ids=_list(rule_ids), sort=sort)
    return S.NextOut(tx_id=None if nxt is None else str(int(nxt)))

# ---- one transaction
@r.get("/tx/{tx_id}/case", response_model=S.CaseBundle)
def case(tx_id: str): return one(S.CaseBundle, s.get_case(tx(tx_id)))
@r.get("/tx/{tx_id}")
def transaction(tx_id: str):
    t = s.get_transaction(tx(tx_id))
    for k in s.DROP_TX_FIELDS: t.pop(k, None)
    for k in s.MASK_TX_FIELDS: t[k] = s.mask(t.get(k))
    return clean(t)
@r.get("/tx/{tx_id}/evidence", response_model=list[S.Evidence])
def evidence(tx_id: str): return one(S.CaseBundle, s.get_case(tx(tx_id))).evidences
@r.get("/tx/{tx_id}/findings", response_model=list[S.Finding])
def findings(tx_id: str): return many(S.Finding, s.get_findings(tx(tx_id)))
@r.get("/tx/{tx_id}/context", response_model=S.Context)
def context(tx_id: str): return one(S.Context, s.get_context(tx(tx_id)))
@r.get("/tx/{tx_id}/profile", response_model=S.Profile)
def profile(tx_id: str): return one(S.Profile, s.get_profile(tx(tx_id)))
@r.get("/tx/{tx_id}/timeline", response_model=list[S.TimelineRow])
def timeline(tx_id: str): return many(S.TimelineRow, s.get_day_timeline(tx(tx_id)))
@r.get("/tx/{tx_id}/precedents", response_model=S.Precedents)
def precedents(tx_id: str): return one(S.Precedents, s.get_precedents(tx(tx_id)))
@r.get("/tx/{tx_id}/score", response_model=S.Score | None)
def score(tx_id: str): return one(S.Score, s.get_score(tx(tx_id)))
@r.get("/tx/{tx_id}/reviews", response_model=list[S.Review])
def reviews(tx_id: str): return many(S.Review, s.get_reviews(tx(tx_id)))

# ---- the only write a screen can make: a human verdict
@r.post("/tx/{tx_id}/review", response_model=list[S.Review], status_code=201)
def review(tx_id: str, body: S.ReviewIn, x_reviewer: Annotated[str, Header()] = "dev"):
    t = tx(tx_id)
    if body.rule_id: s.create_review(t, body.rule_id, body.decision, body.reason_code, body.memo or "", x_reviewer)
    else: s.review_transaction(t, body.decision, body.reason_code, body.memo or "", x_reviewer)
    s.log_event(x_reviewer, "review", dict(tx_id=str(t), decision=body.decision, rule_id=body.rule_id))
    return many(S.Review, s.get_reviews(t))

@r.post("/events", status_code=204)
def events(body: S.EventIn, x_reviewer: Annotated[str, Header()] = "dev"): s.log_event(x_reviewer, body.event, body.payload)

# ---- reference
@r.get("/rules", response_model=list[S.Rule])
def rules(): return many(S.Rule, s.list_rules())
@r.get("/reason-codes", response_model=list[S.ReasonCode])
def reason_codes(): return [S.ReasonCode(code=c, label=l) for c, l in s.REASON_CODES]
@r.get("/policy/{account}", response_model=S.Policy | None)
def policy(account: str): return one(S.Policy, s.get_policy(account))

app.include_router(r)
