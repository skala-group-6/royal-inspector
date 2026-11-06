"""HTTP contract: routes return the same shapes as service functions (ids as strings), and a verdict round-trips through the API."""
import sys, pathlib, re; ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import pytest
from fastapi.testclient import TestClient
pytestmark = pytest.mark.usefixtures("pgdb")
PF, PT = "2025-03-01", "2025-03-31"
ID = re.compile(r"^-?\d+$")

@pytest.fixture(scope="module")
def api(pgdb):
    from api.main import app
    from app import service as s
    if not len(s.list_queue_periods()): s.build_queue(PF, PT, force=True)
    with TestClient(app) as c: yield c

def test_health_and_reference(api):
    assert api.get("/api/health").json()["ok"] is True
    rules = api.get("/api/rules").json(); assert len(rules) >= 19 and {"rule_id", "name", "tier", "explain"} <= set(rules[0])
    assert len(api.get("/api/reason-codes").json()) >= 5
    assert api.get("/api/openapi.json").status_code == 200

def test_queue_items_shape_and_string_ids(api):
    periods = api.get("/api/queues").json(); assert periods and {"period_from", "period_to", "n", "built_at"} <= set(periods[0])
    rows = api.get(f"/api/queues/{PF}/{PT}/items", params=dict(page_size=5)).json()
    assert len(rows) == 5 and all(isinstance(r["tx_id"], str) and ID.match(r["tx_id"]) for r in rows)
    assert {"queue_source", "rules", "n_rules", "sev", "review_status", "score", "score_learned"} <= set(rows[0])
    summ = api.get(f"/api/queues/{PF}/{PT}/summary").json(); assert {r["source"] for r in summ} >= {"rule", "random"}

def test_case_bundle_matches_mock_contract(api):
    import json
    rows = api.get(f"/api/queues/{PF}/{PT}/items", params=dict(sources="rule", page_size=1)).json(); tx = rows[0]["tx_id"]
    c = api.get(f"/api/tx/{tx}/case").json()
    assert set(c) == {"tx_id", "transaction", "evidences", "context", "timeline", "precedents", "score", "policy", "reviews", "profile"}
    mock = json.load(open(ROOT / "web/src/mock/data.json")); m = next(iter(mock["cases"].values()))
    assert set(m["transaction"]) == set(c["transaction"]) and set(m["context"]) == set(c["context"]) and set(m["evidences"][0]) == set(c["evidences"][0])
    assert c["evidences"] and all(isinstance(x["tx_id"], str) for e in c["evidences"] for x in e["related_tx"])
    assert len(c["profile"]["weekly"]) == 13
    for part in ("evidence", "context", "profile", "timeline", "precedents", "score", "reviews"): assert api.get(f"/api/tx/{tx}/{part}").status_code == 200
    assert api.get("/api/tx/999999999999/case").status_code == 404 and api.get("/api/tx/abc/case").status_code == 400

def test_review_roundtrip_and_next(api):
    rows = api.get(f"/api/queues/{PF}/{PT}/items", params=dict(sources="rule", review_status="unreviewed", page_size=2)).json(); tx = rows[0]["tx_id"]
    nxt = api.get("/api/next", params=dict(after=tx, pf=PF, pt=PT)).json()["tx_id"]; assert nxt and nxt != tx
    r = api.post(f"/api/tx/{tx}/review", json=dict(decision="hold", reason_code="need_evidence", memo="api test"), headers={"X-Reviewer": "api_tester"})
    assert r.status_code == 201 and r.json() and r.json()[0]["decision"] == "hold" and r.json()[0]["reviewer"] == "api_tester"
    r2 = api.post(f"/api/tx/{tx}/review", json=dict(decision="ok", reason_code="preapproved"), headers={"X-Reviewer": "api_tester"}).json()
    assert r2[0]["decision"] == "ok" and any(x["superseded"] for x in r2)
    again = api.get(f"/api/queues/{PF}/{PT}/items", params=dict(sources="rule", review_status="reviewed", page_size=500)).json()
    assert tx in {x["tx_id"] for x in again}
    assert api.post(f"/api/tx/{tx}/review", json=dict(decision="maybe")).status_code == 422
    assert api.post("/api/events", json=dict(event="open_case", payload=dict(tx_id=tx))).status_code == 204
