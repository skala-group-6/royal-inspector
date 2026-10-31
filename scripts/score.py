"""Step 2-8: score rule-engine output (table `flags`: rule_id, tx_id) against `ground_truth`.
Prints recall per case and per rule, plus precision on synthetic users. Runs even before any rule exists."""
import duckdb, sys
con = duckdb.connect("data/warehouse.duckdb", read_only=True)
has_flags = con.execute("select count(*) from information_schema.tables where table_name='flags'").fetchall()[0][0] > 0
if not has_flags:
    con.execute("create temp table flags(rule_id varchar, tx_id bigint)").fetchall()
per_rule = con.execute("""
  select g.rule_id, count(*) expected, count(f.tx_id) found, round(100.0*count(f.tx_id)/count(*),1) recall_pct
  from ground_truth g left join flags f on f.tx_id=g.tx_id and f.rule_id=g.rule_id group by 1 order by 1""").df()
per_case = con.execute("""
  select g.case_id, count(distinct g.tx_id) expected_tx, count(distinct f.tx_id) found_tx,
         round(100.0*count(distinct f.tx_id)/count(distinct g.tx_id),1) recall_pct
  from ground_truth g left join flags f on f.tx_id=g.tx_id and f.rule_id=g.rule_id group by 1 order by 1""").df()
prec = con.execute("""
  select f.rule_id, count(*) flagged_synthetic, sum(case when g.tx_id is not null then 1 else 0 end) true_hits
  from flags f join transactions t on t.tx_id=f.tx_id and t.is_synthetic
  left join ground_truth g on g.tx_id=f.tx_id and g.rule_id=f.rule_id group by 1 order by 1""").df()
print("== recall per rule ==\n" + per_rule.to_string(index=False))
print("\n== recall per case ==\n" + per_case.to_string(index=False))
print("\n== precision on synthetic users (flags on planted users that are NOT planted violations = false positives) ==")
print(prec.to_string(index=False) if len(prec) else "(no flags yet)")
total = per_rule.expected.sum(); found = per_rule.found.sum()
print(f"\nOVERALL recall {found}/{total} = {100.0*found/total:.1f}%" + ("" if has_flags else "   [flags table missing: rule engine not built yet]"))
