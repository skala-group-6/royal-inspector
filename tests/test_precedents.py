import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app import service as s

def test_precedents_shape_and_hidden_when_no_overlap():
    tx = int(s.list_flags(rule_ids=["R08_banned_mcc"], synthetic_only=True, page_size=1).tx_id.iloc[0])
    r = s.get_precedents(tx)
    assert r["cases"] and {"title", "cues", "overlap", "only_in_precedent", "only_in_tx", "score"} <= set(r["cases"][0])
    assert all(c["overlap"] for c in r["cases"])

def test_source_case_ranks_first_for_planted_violations():
    """Planted violations know their origin case; that case should be the top precedent for most of them."""
    df = s.q("select distinct t.tx_id, t.case_id from transactions t join ground_truth g using(tx_id) where t.is_synthetic")
    hits = top3 = 0
    for tx_id, case_id in df.itertuples(index=False):
        cases = s.get_precedents(int(tx_id), k=3)["cases"]
        ids = [c["precedent_id"] for c in cases]; me = f"case:{case_id}"
        top_score = cases[0]["score"] if cases else None
        hits += any(c["precedent_id"] == me and c["score"] == top_score for c in cases)  # tie with the top counts (identical signatures)
        top3 += me in ids
    rate1, rate3 = hits / len(df), top3 / len(df)
    print(f"\nsource case top-1 {rate1:.0%}, top-3 {rate3:.0%} over {len(df)} planted tx")
    assert rate1 >= 0.80, f"top-1 {rate1:.0%} below 80%"
