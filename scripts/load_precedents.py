"""Load precedents: disciplinary cases from synth/cases.yaml (kind='case') and, later, reviewed transactions (kind='review').
Re-runnable: replaces only the rows of the kind being loaded. Honors ROYAL_DB."""
import os, sys, yaml, duckdb, pandas as pd
DB = os.environ.get("ROYAL_DB", "data/warehouse.duckdb")
con = duckdb.connect(DB)
con.execute("""CREATE TABLE IF NOT EXISTS precedents(
  precedent_id VARCHAR PRIMARY KEY, kind VARCHAR, title VARCHAR, summary VARCHAR, cues VARCHAR[], rule_ids VARCHAR[],
  account VARCHAR, mcc_group VARCHAR, amount_band VARCHAR, outcome VARCHAR, source VARCHAR)""").fetchall()

def load_cases():
    cases = yaml.safe_load(open("synth/cases.yaml"))["cases"]
    rows = [dict(precedent_id=f"case:{c['id']}", kind="case", title=c["title"], summary=c["summary"], cues=c["cues"], rule_ids=c["precedent_rules"],
                 account=None, mcc_group=None, amount_band=None, outcome=None, source=f"주요시나리오#{c['id']}") for c in cases]
    con.execute("DELETE FROM precedents WHERE kind='case'").fetchall()
    con.register("df", pd.DataFrame(rows)); con.execute("INSERT INTO precedents SELECT * FROM df").fetchall(); con.unregister("df")
    return len(rows)

def load_reviews(reviewers):
    """Promote latest reviews by trusted reviewers to precedents. Not used until real auditor labels exist."""
    if not reviewers: return 0
    ph = ",".join("?" * len(reviewers))
    con.execute("DELETE FROM precedents WHERE kind='review'").fetchall()
    n = con.execute(f"""
      INSERT INTO precedents
      SELECT 'review:' || t.tx_id, 'review', t.account_policy || ' · ' || coalesce(t.mcc_name,''), 
             strftime(t.tx_ts, '%m-%d %H:%M') || ' · ' || t.merchant || ' · ' || cast(t.total as bigint) || '원',
             list_distinct(list(r.reason_code)) , (select list(distinct rule_id order by rule_id) from flags f where f.tx_id=t.tx_id),
             t.account_policy, t.mcc_name, case when t.total<50000 then '<5만' when t.total<200000 then '5~20만' when t.total<500000 then '20~50만' else '50만+' end,
             max(r.decision), min(r.reviewer)
      FROM reviews r JOIN transactions t USING(tx_id)
      WHERE r.superseded_by IS NULL AND r.decision IN ('violation','ok') AND r.reviewer IN ({ph}) AND NOT t.is_synthetic
      GROUP BY t.tx_id, t.account_policy, t.mcc_name, t.tx_ts, t.merchant, t.total""", reviewers).fetchall()
    return con.execute("select count(*) from precedents where kind='review'").fetchall()[0][0]

if __name__ == "__main__":
    reviewers = [a for a in sys.argv[1:]]
    print("cases loaded:", load_cases(), "| review precedents:", load_reviews(reviewers))
    print(con.execute("select kind, count(*), sum(len(rule_ids)) from precedents group by 1").fetchall())
    con.close()
