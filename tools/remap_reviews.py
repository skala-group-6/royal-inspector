"""One-off: after the tx_id key change, re-attach reviews to the same transactions by content.
Usage: ROYAL_DB=... python -I tools/remap_reviews.py data/reviews_backup_2026-11-03.json
Backup rows carry the full review plus match keys (emp_id, tx_ts, total, merchant). Each must match exactly one transaction.
Existing reviews are re-pointed; missing ones (DB rebuilt from scratch) are inserted."""
import sys, json, duckdb
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
rows = json.load(open(sys.argv[1])); con = duckdb.connect(str(paths.DB)); moved = inserted = 0
con.execute("""CREATE TABLE IF NOT EXISTS reviews(review_id VARCHAR, tx_id BIGINT, rule_id VARCHAR, decision VARCHAR, reason_code VARCHAR,
               memo VARCHAR, reviewer VARCHAR, created_at TIMESTAMP, superseded_by VARCHAR)""")
for r in rows:
    hit = con.execute("select tx_id from transactions where emp_id=? and cast(tx_ts as varchar)=? and total=? and merchant=?",
                      [r["emp_id"], r["tx_ts"], r["total"], r["merchant"]]).fetchall()
    assert len(hit) == 1, (r["review_id"], hit)
    new_id = hit[0][0]
    if con.execute("select count(*) from reviews where review_id=?", [r["review_id"]]).fetchone()[0]:
        con.execute("update reviews set tx_id=? where review_id=?", [new_id, r["review_id"]]); moved += 1
    else:
        con.execute("insert into reviews values (?,?,?,?,?,?,?,?,?)", [r["review_id"], new_id, r["rule_id"], r["decision"], r["reason_code"], r["memo"], r["reviewer"], r["created_at"], r.get("superseded_by")]); inserted += 1
con.close(); print(f"re-pointed {moved}, inserted {inserted}, of {len(rows)}")
