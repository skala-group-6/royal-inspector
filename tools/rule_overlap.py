"""Rule overlap report: for every pair of rules, how often they fire on the same real transaction (latest rule run, current tenant).
Pairs above --min (default 0.8 of the smaller rule's hits) are the ones that probably assert the same fact twice — the report
goes to the rule team; the engine never edits rules. Usage: DATABASE_URL=... python -I tools/rule_overlap.py [--min 0.8]"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from db import conn as C

def overlap(con, min_share=0.8) -> pd.DataFrame:
    df = C.q(con, """with f as (select f.tx_id, f.rule_id from current_flags f join tx_active t on t.tx_id = f.tx_id where not t.is_synthetic)
      select a.rule_id rule_a, b.rule_id rule_b, count(*) both_,
             (select count(*) from f where rule_id = a.rule_id) n_a, (select count(*) from f where rule_id = b.rule_id) n_b
      from f a join f b on a.tx_id = b.tx_id and a.rule_id < b.rule_id group by 1, 2 order by 3 desc""")
    if not len(df): return df
    df["share_of_smaller"] = (df.both_ / df[["n_a", "n_b"]].min(axis=1)).round(3)
    return df[df.share_of_smaller >= min_share].reset_index(drop=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--min", type=float, default=0.8); a = ap.parse_args()
    con = C.connect(); df = overlap(con, a.min); con.close()
    print(f"rule pairs firing together on >= {a.min:.0%} of the smaller rule's real hits:")
    print(df.to_string(index=False) if len(df) else "(none)")
