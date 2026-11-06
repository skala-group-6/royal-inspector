"""Score rule-engine output (flag table: rule_id, tx_id) against `ground_truth` for the current tenant.
Prints recall per case and per rule, plus precision on synthetic users. Runs even before any rule has run.
Importable: score.main(table, con) — called by run_rules.py on the same connection (partial runs use a temp table)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import conn as C

def main(table="current_flags", con=None):
    own = con is None; con = con or C.connect()
    has_flags = C.one(con, "select to_regclass(%s) is not null", [table])
    if not has_flags:
        table = "flags_empty"; con.execute("create temp table flags_empty(rule_id text, tx_id bigint)")
    per_rule = C.q(con, f"""
      select g.rule_id, count(*) expected, count(f.tx_id) found, round(100.0*count(f.tx_id)/count(*),1) recall_pct
      from ground_truth g left join {table} f on f.tx_id=g.tx_id and f.rule_id=g.rule_id where g.tenant_id=tenant() group by 1 order by 1""")
    per_case = C.q(con, f"""
      select g.case_id, count(distinct g.tx_id) expected_tx, count(distinct f.tx_id) found_tx,
             round(100.0*count(distinct f.tx_id)/count(distinct g.tx_id),1) recall_pct
      from ground_truth g left join {table} f on f.tx_id=g.tx_id and f.rule_id=g.rule_id where g.tenant_id=tenant() group by 1 order by 1""")
    prec = C.q(con, f"""
      select f.rule_id, count(*) flagged_synthetic, sum(case when g.tx_id is not null then 1 else 0 end) true_hits
      from {table} f join transactions t on t.tenant_id=tenant() and t.tx_id=f.tx_id and t.is_synthetic
      left join ground_truth g on g.tenant_id=tenant() and g.tx_id=f.tx_id and g.rule_id=f.rule_id group by 1 order by 1""")
    if own: con.close()
    print("== recall per rule ==\n" + per_rule.to_string(index=False))
    print("\n== recall per case ==\n" + per_case.to_string(index=False))
    print("\n== precision on synthetic users (flags on planted users that are NOT planted violations = false positives) ==")
    print(prec.to_string(index=False) if len(prec) else "(no flags yet)")
    total = int(per_rule.expected.sum()); found = int(per_rule.found.sum())
    print(f"\nOVERALL recall {found}/{total} = {100.0*found/total:.1f}%" + ("" if has_flags else "   [no flags: rule engine not run yet]"))
    return found, total

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "current_flags")
