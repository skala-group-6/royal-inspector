"""Deterministic keys (plan 1-D). Pack manifest checks are added in step E."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import pandas as pd
from keys import det_ids, det_id

COLS = ["sap_doc_no", "acquirer_no", "approval_no", "tx_date", "tx_time", "total", "emp_id"]
def frame(rows): return pd.DataFrame(rows, columns=COLS)

def test_ids_independent_of_row_order():
    rows = [("A1", "X", 1, "2025-03-01", "12:00:00", 10000.0, 7), ("A2", None, 2, "2025-03-02", "13:00:00", 20000.0, 8), ("A3", "Y", pd.NA, "2025-03-03", None, 500.0, 9)]
    a = det_ids(frame(rows), COLS); b = det_ids(frame(rows[::-1]), COLS)
    assert set(a) == set(b) and a.is_unique and str(a.dtype) == "int64"

def test_exact_duplicates_get_distinct_ids_and_same_set():
    rows = [("A1", "X", 1, "2025-03-01", "12:00:00", 10000.0, 7)] * 3 + [("B", "X", 1, "2025-03-01", "12:00:00", 10000.0, 7)]
    a = det_ids(frame(rows), COLS); b = det_ids(frame(rows[::-1]), COLS)
    assert a.is_unique and set(a) == set(b)

def test_float_and_int_amounts_hash_equal():
    f = det_ids(frame([("A1", "X", 1, "2025-03-01", "12:00:00", 10000.0, 7)]), COLS).iloc[0]
    i = det_ids(frame([("A1", "X", 1, "2025-03-01", "12:00:00", 10000, 7)]), COLS).iloc[0]
    assert f == i

def test_synthetic_key_is_stable():
    assert det_id("SY", "SY000000001") == det_id("SY", "SY000000001") != det_id("SY", "SY000000002")


def test_manifest_paths_exist_and_default_pack_is_corp_card():
    sys.path.insert(0, str(ROOT)); import importlib, paths as P
    assert P.PACK_NAME == "corp_card" and P.PACK_DIR == (ROOT / "packs" / "corp_card").resolve()
    for p in (P.RULES_CATALOG, P.RULES_SQL_DIR, P.FEATURES_CATALOG, P.WEAK_LABELS, P.CASES):
        assert p is not None and p.exists(), p
    assert P.FUNCTIONS is None or P.FUNCTIONS.exists()
    import yaml
    stems = {f.stem for f in P.RULES_SQL_DIR.glob("R*.sql")}; cat = set(yaml.safe_load(open(P.RULES_CATALOG))["rules"])
    assert stems and stems <= cat, stems - cat   # every rule SQL is declared in the catalog
    assert P.RAW_GLOB

def test_no_hardcoded_pack_paths_in_engine_code():
    import re
    bad = re.compile(r'"(rules|features|labels|synth)/[^"]*\.(yaml|sql)"|ROOT / "(rules|features|labels|synth)"')
    hits = [f for f in list((ROOT / "scripts").glob("*.py")) + [ROOT / "features" / "executor.py", ROOT / "app" / "service.py"] if bad.search(f.read_text())]
    assert not hits, hits


def test_rule_catalog_contract():
    """The catalog is the vessel the rule team fills: every rule has the fields the engine and the screen rely on, and every
    {placeholder} in fact/brief is a key the rule's SQL actually emits in evidence (or a derived key the service adds)."""
    import re, yaml
    sys.path.insert(0, str(ROOT)); import paths as P
    cat = yaml.safe_load(open(P.RULES_CATALOG))["rules"]
    derived = {"total_won", "date_md", "merchant_sigungu_short", "approver_sigungu_short", "home_sigungu_short", "work_sigungu_short"}
    for rid, r in cat.items():
        for k in ("name", "tier", "cluster", "fact_key", "fact", "brief", "explain", "policy_ref"): assert r.get(k), (rid, k)
        assert r["tier"] in ("violation", "advisory") and set(r["brief"]) == {"value", "verdict"}, rid
        sql = P.RULES_SQL_DIR / f"{rid}.sql"
        if not sql.exists(): assert str(r.get("data_ready")) == "no", f"{rid}: no SQL but data_ready != no"; continue
        keys = set(re.findall(r"'([a-z_0-9]+)'\s*,", sql.read_text())) | derived
        used = set(re.findall(r"\{([a-z_0-9]+)\}", r["fact"] + r["brief"]["value"] + r["brief"]["verdict"]))
        assert used <= keys, f"{rid}: placeholders not in evidence: {sorted(used - keys)}"
