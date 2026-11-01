"""Step 3.9: score every tx_features row with the chosen model (models/LATEST or --version) → tx_score(tx_id, score, model_version, top_features).
top_features is JSON [[feature, contribution, human_text], ...]. Honors ROYAL_DB."""
from __future__ import annotations
import os, sys, json, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd, duckdb
from features.executor import load_catalog
from models.base import load_model

AUX_TEXT = {"n_violation_rules": "걸린 위반등급 규칙 수", "n_rules": "걸린 규칙 수", "total": "금액"}

def score(con, models_dir="models", version=None, quiet=False) -> int:
    mdir = Path(models_dir); version = version or (mdir / "LATEST").read_text().strip()
    manifest = json.loads((mdir / version / "manifest.json").read_text()); model = load_model(mdir / version / "model.pkl")
    learned = load_model(mdir / version / "model_learned.pkl") if (mdir / version / "model_learned.pkl").exists() else None
    cat = load_catalog(); desc = {n: f.get("describe", n) for n, f in cat["features"].items()}
    df = con.execute(f"""select f.*, t.total, coalesce(a.n_rules,0) n_rules, coalesce(a.n_violation_rules,0) n_violation_rules
        from tx_features f join tx_active t using(tx_id)
        left join (select tx_id, count(distinct rule_id) n_rules, count(distinct case when severity='violation' then rule_id end) n_violation_rules from flags group by 1) a using(tx_id)
        order by f.tx_id""").df()
    X = df[manifest["features"]].astype(float); aux = df[["n_rules", "n_violation_rules", "total"]].astype(float)
    s = np.clip(np.asarray(model.predict(X, aux), dtype=float), 0, 1); ex = model.explain(X, aux, 3)
    sl = np.clip(np.asarray(learned.predict(X, aux), dtype=float), 0, 1) if learned is not None else np.full(len(df), np.nan)
    exl = learned.explain(X, aux, 3) if learned is not None else [[] for _ in range(len(df))]
    def human(name, contrib, i):
        v = aux[name].iloc[i] if name in aux else X[name].iloc[i]
        txt = AUX_TEXT.get(name, desc.get(name, name)); vs = "" if pd.isna(v) else f" {v:,.2f}".rstrip("0").rstrip(".")
        return f"{txt}{vs} ({'↑' if contrib > 0 else '↓'})"
    pack = lambda e, i: json.dumps([[n, round(c, 6), human(n, c, i)] for n, c in e[i]], ensure_ascii=False)
    out = pd.DataFrame(dict(tx_id=df.tx_id, score=np.round(s, 6), model_version=version, top_features=[pack(ex, i) for i in range(len(df))],
                            score_learned=np.round(sl, 6), learned_name=manifest.get("best_learned"), top_features_learned=[pack(exl, i) for i in range(len(df))]))
    con.execute("CREATE OR REPLACE TABLE tx_score(tx_id BIGINT, score DOUBLE, model_version VARCHAR, top_features VARCHAR, score_learned DOUBLE, learned_name VARCHAR, top_features_learned VARCHAR)").fetchall()
    con.register("df_out", out); con.execute("INSERT INTO tx_score SELECT * FROM df_out").fetchall(); con.unregister("df_out")
    if not quiet: print(f"tx_score: {len(out):,} rows · chosen {manifest['chosen']} · learned {manifest.get('best_learned')} · score>0.5: {(out.score>0.5).mean():.1%} · learned>0.5: {np.nanmean(out.score_learned>0.5):.1%}")
    return len(out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--models-dir", default="models"); ap.add_argument("--version", default=None); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(); con = duckdb.connect(os.environ.get("ROYAL_DB", "data/warehouse.duckdb")); score(con, a.models_dir, a.version, a.quiet); con.close()
