"""Export the React mock (web/src/mock/data.json) from a built database through the same service functions the API will expose.
Usage: DATABASE_URL=$(.venv/bin/python scripts/db_clone.py --name mock) python -I tools/export_mock.py [--period 2025-03-01 2025-03-31] [--out web/src/mock/data.json]

Selection is deliberately mixed so the review screen is exercised at its extremes: multi-violation rows, advisory-only rows,
model-recommended and random-sample rows (no rules → no evidence), and already-reviewed rows. PII that the screen never shows
(home/approver addresses, unmasked approver/reviewer names) is dropped before writing; employee names are masked by the service layer."""
import sys, json, argparse, datetime as dt, math
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import paths  # noqa: F401  (resolves the pack)
from app import service as s

DROP_TX_FIELDS = {"home_addr", "approver_addr", "work_site_addr", "reviewer", "tenant_id", "load_id"}  # PII the screen never shows + storage-only keys
MASK_TX_FIELDS = {"approver"}  # names are masked like emp_name; ids are not PII

ID_KEYS = {"tx_id", "cancel_of_tx_id"}

def clean(o, key=None):
    """JSON-safe: DataFrames → records, numpy/pandas scalars → python, NaN/NaT → None, dates → ISO.
    tx ids are 64-bit (content hash) and exceed JavaScript's safe integer range, so every id field is written as a string."""
    if key in ID_KEYS and o is not None and not (isinstance(o, float) and math.isnan(o)): return str(int(o))
    if isinstance(o, pd.DataFrame): return [clean(r) for r in o.to_dict(orient="records")]
    if isinstance(o, dict): return {str(k): clean(v, k) for k, v in o.items()}
    if isinstance(o, (list, tuple, np.ndarray)): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return None if math.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if o is pd.NaT or o is None: return None
    if isinstance(o, (pd.Timestamp, dt.datetime)): return o.isoformat(timespec="seconds")
    if isinstance(o, dt.date): return o.isoformat()
    if isinstance(o, dt.time): return o.isoformat()
    try:
        if pd.isna(o): return None
    except (TypeError, ValueError): pass
    return o

def pick(period) -> list[int]:
    q = s.list_queue(*period, page_size=10000)
    def take(df, n): return df.tx_id.head(n).tolist()
    rule = q[q.queue_source == "rule"]
    chosen = []
    chosen += take(rule[rule.sev == 2].sort_values(["n_rules", "total"], ascending=False), 5)       # many violations, big amounts
    chosen += take(rule[(rule.sev == 2) & (rule.n_rules == 1)].sort_values("total"), 2)             # single violation, small amount
    chosen += take(rule[rule.sev == 1], 3)                                                           # advisory only
    chosen += take(q[q.queue_source == "model"], 3)
    chosen += take(q[q.queue_source == "random"], 3)
    chosen += take(q[q.review_status != "unreviewed"], 3)                                            # already reviewed
    chosen += take(rule[rule.rules.map(lambda r: any(x.startswith("R03") or x.startswith("R06") for x in r))], 2)  # rows with related tx
    seen, out = set(), []
    for t in chosen:
        if t not in seen: seen.add(t); out.append(int(t))
    return out

def bundle(tx_id: int) -> dict:
    t = s.get_transaction(tx_id)
    for k in DROP_TX_FIELDS: t.pop(k, None)
    for k in MASK_TX_FIELDS: t[k] = s.mask(t.get(k))
    evs = []
    for e in s.get_evidence(tx_id):
        h, d = s.evidence_headline(e["rule_id"], e["evidence"], t)
        evs.append(dict(e, headline=h, detail=d, citation=s.policy_citation(e["rule_id"], t), explain=s.rule_explain(e["rule_id"])))
    return dict(tx_id=tx_id, transaction=t, evidences=evs, context=s.get_context(tx_id), timeline=s.get_day_timeline(tx_id),
                precedents=s.get_precedents(tx_id), score=s.get_score(tx_id), policy=s.get_policy(t.get("account_policy")), reviews=s.get_reviews(tx_id),
                profile=s.get_profile(tx_id))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--period", nargs=2, default=["2025-03-01", "2025-03-31"]); ap.add_argument("--out", default=str(ROOT / "web/src/mock/data.json"))
    a = ap.parse_args(); period = tuple(a.period)
    ids = pick(period)
    queue = s.list_queue(*period, page_size=10000); queue = queue[queue.tx_id.isin(ids)].drop(columns=["one"], errors="ignore")
    order = {t: i for i, t in enumerate(ids)}; queue = queue.sort_values(by="tx_id", key=lambda c: c.map(order))
    data = dict(period=dict(period_from=period[0], period_to=period[1]), queue=queue, cases={str(t): bundle(t) for t in ids},
                rules=s.list_rules(), reason_codes=[dict(code=c, label=l) for c, l in s.REASON_CODES], summary=s.get_queue_summary(*period))
    data = clean(data)
    # shape guard: what the UI types (web/src/types.ts) rely on
    for c in data["cases"].values():
        assert {"tx_id", "transaction", "evidences", "context", "timeline", "precedents", "score", "policy", "reviews", "profile"} <= set(c)
        assert len(c["profile"]["weekly"]) == 13 and c["profile"]["amount"]["user"]["n"] >= 0
        assert not (DROP_TX_FIELDS & set(c["transaction"])), "PII field leaked"
    assert all(isinstance(r["tx_id"], str) for r in data["queue"]) and set(data["cases"]) == {r["tx_id"] for r in data["queue"]}, "ids must be strings and match"
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    by_src = queue.queue_source.value_counts().to_dict(); reviewed = int((queue.review_status != "unreviewed").sum())
    print(f"wrote {a.out}: {len(ids)} cases · sources {by_src} · reviewed {reviewed} · evidences {sum(len(c['evidences']) for c in data['cases'].values())}")

if __name__ == "__main__":
    main()
