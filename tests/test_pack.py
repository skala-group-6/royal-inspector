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
