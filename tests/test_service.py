import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app import service as s

def test_rules_and_summary():
    assert len(s.list_rules()) >= 19
    sm = s.get_summary(); assert sm.flagged.sum() > 0 and {"rule_id", "hit_rate_pct"} <= set(sm.columns)

def test_list_and_evidence():
    df = s.list_flags(rule_ids=["R03_split_payment"], synthetic_only=True, page_size=5)
    assert len(df) > 0 and all("*" in n or len(n) < 2 for n in df.emp_name)
    ev = s.get_evidence(int(df.tx_id.iloc[0]))
    assert any(e["rule_id"] == "R03_split_payment" for e in ev)
    e = next(e for e in ev if e["rule_id"] == "R03_split_payment")
    assert "분 안에" in e["evidence_text"] and len(e["related_tx"]) >= 1

def test_context():
    tx = int(s.list_flags(rule_ids=["R12_card_lending"], synthetic_only=True, page_size=1).tx_id.iloc[0])
    c = s.get_context(tx)
    assert len(c["access_same_day"]) >= 1 and c["peer"] is not None and "flagged_tx" in c["history"]

def test_review_roundtrip():
    row = s.list_flags(synthetic_only=True, page_size=1).iloc[0]; tx, rule = int(row.tx_id), row.rules[0]
    r1 = s.create_review(tx, rule, "hold", "need_evidence", "test", "tester")
    r2 = s.create_review(tx, rule, "ok", "preapproved", "test2", "tester")
    rv = s.get_reviews(tx)
    assert rv[rv.review_id == r1["review_id"]].superseded.iloc[0] and not rv[rv.review_id == r2["review_id"]].superseded.iloc[0]
    assert s.list_flags(review_status="reviewed", synthetic_only=True).tx_id.isin([tx]).any()
    # cleanup
    s.con().execute("delete from reviews where reviewer='tester'").fetchall()


def test_tier_and_citation():
    r = s.list_rules(); assert set(r.tier) == {"violation", "advisory"} and r.explain.str.len().gt(10).all()
    tx = int(s.list_flags(rule_ids=["R08_banned_mcc"], synthetic_only=True, page_size=1).tx_id.iloc[0])
    t = s.get_transaction(tx); c = s.policy_citation("R08_banned_mcc", t)
    assert c and ("Don'ts" in c or "규정" in c or "시나리오" in c)


def test_list_tier_marker():
    df = s.list_flags(rule_ids=["R08_banned_mcc"], page_size=5)
    assert (df.sev == 2).all(), "rows flagged by a violation-tier rule must carry sev=2"


def test_profile():
    tx = int(s.list_flags(rule_ids=["R16_amount_outlier"], synthetic_only=True, page_size=1).tx_id.iloc[0])
    p = s.get_profile(tx)
    assert set(p) == {"amount", "weekly"} and set(p["amount"]) == {"this", "user", "peer"}
    for side in ("user", "peer"):
        d = p["amount"][side]; assert set(d) == {"n", "p25", "p50", "p75", "p90"}
        if d["n"]: assert d["p25"] <= d["p50"] <= d["p75"] <= d["p90"]
    assert len(p["weekly"]) == 13 and list(p["weekly"].columns) == ["week_start", "flagged", "violations"]
    assert (p["weekly"].violations <= p["weekly"].flagged).all()
    # point-in-time: user n must equal the feature table's prior-tx count for this tx
    f = s.q("select user__all__n_tx from tx_features where tx_id=?", [tx])
    if len(f) and f.iloc[0, 0] is not None: assert p["amount"]["user"]["n"] == int(f.iloc[0, 0])
    # no future rows: the tx itself is excluded
    row = s.q("select emp_id, tx_ts from transactions where tx_id=?", [tx]).iloc[0]
    n_strict = int(s.q("select count(*) from tx_active where emp_id=? and tx_ts<? and total>0", [int(row.emp_id), row.tx_ts]).iloc[0, 0])
    assert p["amount"]["user"]["n"] == n_strict
