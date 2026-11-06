"""One-off: re-attach reviews to the same transactions by content (e.g. after a key change or a database rebuild).
Usage: DATABASE_URL=... python -I tools/remap_reviews.py data/reviews_backup_2026-11-03.json
Backup rows carry the full review plus match keys (emp_id, tx_ts, total, merchant) and the reviewer *name*. Each must match exactly one
transaction of the current tenant. Existing reviews are re-pointed; missing ones (DB rebuilt from scratch) are inserted."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import conn as C
from app import service as s
rows = json.load(open(sys.argv[1])); con = C.connect(autocommit=False); moved = inserted = 0
with con.transaction():
    for r in rows:
        hit = C.q(con, "select tx_id from transactions where tenant_id = tenant() and emp_id = %s and tx_ts = %s::timestamptz and total = %s and merchant = %s",
                  [r["emp_id"], r["tx_ts"], r["total"], r["merchant"]]).tx_id.tolist()
        assert len(hit) == 1, (r["review_id"], hit)
        new_id = int(hit[0])
        if C.one(con, "select count(*) from reviews where tenant_id = tenant() and review_id = %s", [r["review_id"]]):
            C.execute(con, "update reviews set tx_id = %s where tenant_id = tenant() and review_id = %s", [new_id, r["review_id"]]); moved += 1
        else:
            C.execute(con, "insert into reviews(tenant_id, review_id, tx_id, rule_id, decision, reason_code, memo, reviewer_id, created_at, superseded_by) values (tenant(), %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                      [r["review_id"], new_id, r["rule_id"], r["decision"], r["reason_code"], r["memo"], s.reviewer_id(r["reviewer"]), r["created_at"], r.get("superseded_by")]); inserted += 1
con.commit(); con.close(); print(f"re-pointed {moved}, inserted {inserted}, of {len(rows)}")
