"""One-off: after the tx_id key change, re-attach existing reviews to the same transactions by content.
Usage: ROYAL_DB=... python -I tools/remap_reviews.py data/reviews_backup_2026-11-03.json
Backup rows: {review_id, old_tx_id, rule_id, emp_id, tx_ts, total, merchant}. Each must match exactly one transaction."""
import sys, json, duckdb
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
rows = json.load(open(sys.argv[1])); con = duckdb.connect(str(paths.DB)); n = 0
for r in rows:
    hit = con.execute("select tx_id from transactions where emp_id=? and cast(tx_ts as varchar)=? and total=? and merchant=?",
                      [r["emp_id"], r["tx_ts"], r["total"], r["merchant"]]).fetchall()
    assert len(hit) == 1, (r["review_id"], hit)
    if con.execute("select count(*) from reviews where review_id=?", [r["review_id"]]).fetchone()[0]:
        con.execute("update reviews set tx_id=? where review_id=?", [hit[0][0], r["review_id"]]); n += 1
    else:
        print("review missing in DB, skipped:", r["review_id"])
con.close(); print(f"remapped {n}/{len(rows)}")
