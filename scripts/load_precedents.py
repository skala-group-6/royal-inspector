"""Load precedents: disciplinary cases from the pack cases file (paths.CASES) as the shared library (kind='case', tenant_id null) and,
later, reviewed transactions of the current tenant (kind='review'). Re-runnable: replaces only the rows of the kind being loaded. Uses DATABASE_URL."""
import os, sys, yaml, pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
from db import conn as C
con = C.connect()

def load_cases():
    cases = yaml.safe_load(open(paths.CASES))["cases"]
    rows = [dict(precedent_id=f"case:{c['id']}", kind="case", title=c["title"], summary=c["summary"], cues=c["cues"], rule_ids=c["precedent_rules"],
                 account=None, mcc_group=None, amount_band=None, outcome=None, source=f"주요시나리오#{c['id']}") for c in cases]
    C.execute(con, "DELETE FROM precedents WHERE kind='case' AND tenant_id IS NULL")
    C.write_df(con, "precedents", pd.DataFrame(rows), tenant=False)
    return len(rows)

def load_reviews(reviewers):
    """Promote latest reviews by trusted reviewers (reviewers.name) to precedents. Not used until real auditor labels exist."""
    if not reviewers: return 0
    C.execute(con, "DELETE FROM precedents WHERE kind='review' AND tenant_id = tenant()")
    C.execute(con, """
      INSERT INTO precedents(tenant_id, precedent_id, kind, title, summary, cues, rule_ids, account, mcc_group, amount_band, outcome, source)
      SELECT tenant(), 'review:' || t.tx_id, 'review', t.account_policy || ' · ' || coalesce(t.mcc_name,''),
             to_char(t.tx_ts, 'MM-DD HH24:MI') || ' · ' || t.merchant || ' · ' || cast(t.total as bigint) || '원',
             coalesce(array_agg(DISTINCT r.reason_code) FILTER (WHERE r.reason_code IS NOT NULL), '{}'::text[]),
             coalesce((SELECT array_agg(DISTINCT rule_id ORDER BY rule_id) FROM current_flags f WHERE f.tx_id = t.tx_id), '{}'::text[]),
             t.account_policy, t.mcc_name, CASE WHEN t.total<50000 THEN '<5만' WHEN t.total<200000 THEN '5~20만' WHEN t.total<500000 THEN '20~50만' ELSE '50만+' END,
             max(r.decision), min(v.name)
      FROM latest_reviews r JOIN reviewers v ON v.tenant_id = r.tenant_id AND v.reviewer_id = r.reviewer_id
      JOIN transactions t ON t.tenant_id = r.tenant_id AND t.tx_id = r.tx_id
      WHERE r.decision IN ('violation','ok') AND v.name = ANY(%s) AND NOT t.is_synthetic
      GROUP BY t.tx_id, t.account_policy, t.mcc_name, t.tx_ts, t.merchant, t.total""", [list(reviewers)])
    return C.one(con, "select count(*) from precedents where kind='review' and tenant_id = tenant()")

if __name__ == "__main__":
    reviewers = [a for a in sys.argv[1:]]
    print("cases loaded:", load_cases(), "| review precedents:", load_reviews(reviewers))
    print(C.q(con, "select kind, count(*) n, sum(cardinality(rule_ids)) rules from precedents group by 1").values.tolist())
    con.close()
