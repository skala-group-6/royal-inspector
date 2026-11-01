"""Feature executor: turns features/catalog.yaml declarations into one SQL statement and materializes tx_features.
Point-in-time by construction: window frames end at INTERVAL 1 MICROSECOND PRECEDING (self and simultaneous rows excluded);
the correlated strategy uses h.tx_ts < t.tx_ts. Both must agree (validated by scripts/validate_features.py)."""
from __future__ import annotations
import re, hashlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "features" / "catalog.yaml"
MACROS = ROOT / "rules" / "macros.sql"
KEY_COLS = ["tx_id", "tx_ts", "tx_date", "emp_id", "is_synthetic"]

def load_catalog(path: Path | str = CATALOG) -> dict:
    cat = yaml.safe_load(open(path))
    ents, wins, feats = cat["entities"], cat["windows"], cat["features"]
    bad_name, bad_sql = re.compile(cat["forbidden_name"]), re.compile(cat["forbidden_sql"])
    for name, f in feats.items():
        kind = f.get("kind", "agg")
        if f.get("group") != "history" and bad_name.search(name):
            raise ValueError(f"{name}: rule-derived names are forbidden outside the history group")
        for k in ("where", "predicate", "expr", "of"):
            if k in f and bad_sql.search(str(f[k])):
                raise ValueError(f"{name}.{k}: free SQL / rule tables are not allowed: {f[k]}")
        if kind == "agg":
            if f["entity"] not in ents: raise ValueError(f"{name}: unknown entity {f['entity']}")
            if f["window"] not in wins: raise ValueError(f"{name}: unknown window {f['window']}")
            if not name.startswith(f"{f['entity']}__{f['window']}__"): raise ValueError(f"{name}: name must start with {f['entity']}__{f['window']}__")
            if f["agg"] in ("ratio_to_quantile", "ratio_predicate", "percentile_of_value"):
                n = f.get("n_obs")
                if not n or n not in feats or feats[n].get("agg") != "count" or feats[n]["entity"] != f["entity"] or feats[n]["window"] != f["window"]:
                    raise ValueError(f"{name}: ratio/percentile features need an n_obs count on the same entity+window")
            if wins[f["window"]].get("lookahead") or f["agg"] == "until_next_minutes": f["lookahead"] = True
        elif kind == "column":
            if not name.startswith("ctx__"): raise ValueError(f"{name}: column features must be named ctx__*")
        elif kind == "history":
            if not name.startswith("hist__") or f.get("group") != "history": raise ValueError(f"{name}: history features must be hist__* in group history")
        else: raise ValueError(f"{name}: unknown kind {kind}")
    return cat

# ---------- SQL rendering ----------
def _keys(cat, f): return cat["entities"][f["entity"]]
def _null_guard(keys, expr): return "CASE WHEN " + " OR ".join(f"t.{k} IS NULL" for k in keys) + f" THEN NULL ELSE {expr} END"
def _where_case(f, val="1"): return f"CASE WHEN {f['where']} THEN {val} END" if f.get("where") else val
def _round(expr): return f"round(({expr})::DOUBLE, 6)"

def _frame(cat, f):
    w = cat["windows"][f["window"]]
    lo = "UNBOUNDED PRECEDING" if w.get("lo") is None else f"{w['lo']} PRECEDING"
    return f"RANGE BETWEEN {lo} AND INTERVAL 1 MICROSECOND PRECEDING"

def _over(cat, f): return f"OVER (PARTITION BY {', '.join(_keys(cat, f))} ORDER BY tx_ts {_frame(cat, f)})"
def _over_day(cat, f): return f"OVER (PARTITION BY {', '.join(_keys(cat, f))}, tx_date)"

def render_window(cat, name, f) -> str:
    agg, keys = f["agg"], _keys(cat, f)
    of = f.get("of", "total")
    same_day = cat["windows"][f["window"]].get("kind") == "calendar_day"
    if agg == "count":
        if same_day: e = f"count({_where_case(f)}) {_over_day(cat, f)} - ({_where_case(f, '1')} IS NOT NULL)::int"
        else: e = f"count({_where_case(f)}) {_over(cat, f)}"
    elif agg == "sum": e = f"sum({_where_case(f, of)}) {_over(cat, f)}"
    elif agg == "quantile": e = f"quantile_cont({_where_case(f, of)}, {f['p']}) {_over(cat, f)}"
    elif agg == "ratio_to_quantile": e = f"t.{of} / nullif(quantile_cont({_where_case(f, of)}, {f['p']}) {_over(cat, f)}, 0)"
    elif agg == "ratio_predicate":
        if "t." in f["predicate"]: return render_correlated(cat, name, f)  # focal-row reference needs the correlated form
        flag = f"(CASE WHEN {f['predicate']} THEN 1 ELSE 0 END)"
        e = f"avg({_where_case(f, flag)}) {_over(cat, f)}"
    elif agg == "count_distinct":
        e = f"count(DISTINCT {_where_case(f, of)}) {_over_day(cat, f) if same_day else _over(cat, f)}"
    elif agg == "since_last_minutes":
        prev = f"(SELECT max(h.tx_ts) FROM base h WHERE {' AND '.join(f'h.{k} = t.{k}' for k in keys)} AND h.tx_ts < t.tx_ts AND NOT h.time_is_dummy)"
        e = f"CASE WHEN t.time_is_dummy THEN NULL ELSE datediff('minute', {prev}, t.tx_ts) END"
    elif agg == "until_next_minutes":
        e = f"CASE WHEN t.time_is_dummy THEN NULL ELSE datediff('minute', t.tx_ts, lead(tx_ts) OVER (PARTITION BY {', '.join(keys)} ORDER BY tx_ts, tx_id)) END"
    elif agg == "percentile_of_value": return render_correlated(cat, name, f)
    else: raise ValueError(f"{name}: unsupported agg {agg}")
    return _round(_null_guard(keys, e))

def render_correlated(cat, name, f) -> str:
    agg, keys, of = f["agg"], _keys(cat, f), f.get("of", "total")
    w = cat["windows"][f["window"]]
    if w.get("kind") == "calendar_day": return render_window(cat, name, f)  # same_day stays on the window path
    cond = " AND ".join(f"h.{k} = t.{k}" for k in keys) + " AND h.tx_ts < t.tx_ts"
    if w.get("lo"): cond += f" AND h.tx_ts >= t.tx_ts - {w['lo']}"
    if f.get("where"): cond += f" AND ({f['where']})"
    sub = lambda sel: f"(SELECT {sel} FROM base h WHERE {cond})"
    if agg == "count": e = sub("count(*)")
    elif agg == "sum": e = sub(f"sum(h.{of})")
    elif agg == "quantile": e = sub(f"quantile_cont(h.{of}, {f['p']})")
    elif agg == "ratio_to_quantile":
        pq = f["p"]; e = f"t.{of} / nullif({sub(f'quantile_cont(h.{of}, {pq})')}, 0)"
    elif agg == "ratio_predicate": e = sub(f"avg(CASE WHEN {f['predicate']} THEN 1 ELSE 0 END)")
    elif agg == "count_distinct": e = sub(f"count(DISTINCT h.{of})")
    elif agg == "percentile_of_value": e = sub(f"100.0 * count(*) FILTER (WHERE h.{of} < t.{of}) / nullif(count(*), 0)")
    elif agg in ("since_last_minutes", "until_next_minutes"): return render_window(cat, name, f)  # since_last is already correlated; until_next is lookahead
    else: raise ValueError(f"{name}: unsupported agg {agg}")
    return _round(_null_guard(keys, e))

def render_history(name, f) -> str:
    # only built with with_history=True; counts prior flagged tx of the same employee
    return "(SELECT count(DISTINCT fl.tx_id) FROM flags fl JOIN transactions ft ON ft.tx_id = fl.tx_id WHERE ft.emp_id = t.emp_id AND ft.tx_ts < t.tx_ts)"

def render_feature(cat, name, f, strategy="window", with_history=False):
    kind = f.get("kind", "agg")
    if kind == "history": return render_history(name, f) if with_history else None
    if kind == "column": return f["expr"]
    return render_window(cat, name, f) if strategy == "window" else render_correlated(cat, name, f)

def build_sql(cat, strategy="window", with_history=False, source=None, target="tx_features", focal_ids=None) -> tuple[str, list[str]]:
    source = source or cat["source"]
    cols, names = [], []
    for name, f in cat["features"].items():
        kind = f.get("kind", "agg")
        if kind == "history":
            if not with_history: continue
            e = render_history(name, f)
        elif kind == "column": e = _round(f["expr"]) if "::int" not in f["expr"] and "hour(" not in f["expr"] and "dayofweek" not in f["expr"] else f["expr"]
        else: e = render_window(cat, name, f) if strategy == "window" else render_correlated(cat, name, f)
        PIT_MARKERS = ("INTERVAL 1 MICROSECOND PRECEDING", "h.tx_ts < t.tx_ts", "ft.tx_ts < t.tx_ts")
        if kind != "column" and not f.get("lookahead") and not any(m in e for m in PIT_MARKERS):
            raise AssertionError(f"{name}: rendered SQL is not point-in-time: {e[:120]}")
        cols.append(f"{e} AS {name}"); names.append(name)
    sql = f"""CREATE OR REPLACE TABLE {target} AS
WITH base AS (SELECT * FROM {source})
SELECT {', '.join('t.' + k for k in KEY_COLS)}, {', '.join(cols)}
FROM base t{(' WHERE t.tx_id IN (' + ','.join(str(int(i)) for i in focal_ids) + ')') if focal_ids else ''} ORDER BY t.tx_id"""
    return sql, names

def build(con, strategy="window", with_history=False, source=None, target="tx_features", quiet=False, focal_ids=None) -> dict:
    cat = load_catalog()
    con.execute(MACROS.read_text()).fetchall()
    sql, names = build_sql(cat, strategy, with_history, source, target, focal_ids)
    con.execute(sql).fetchall()
    n = con.execute(f"select count(*) from {target}").fetchall()[0][0]
    h = con.execute(f"select md5(string_agg(md5(t::varchar), '' order by tx_id)) from {target} t").fetchall()[0][0]
    if target == "tx_features": create_entity_stats_view(con, cat, names)
    info = dict(catalog_version=cat["version"], strategy=strategy, rows=n, n_features=len(names), hash=h, features=names)
    if not quiet: print(f"{target}: {n:,} rows × {len(names)} features (catalog v{cat['version']}, {strategy}) hash {h[:12]}")
    return info

def create_entity_stats_view(con, cat, names):
    """Long-form view over tx_features: (tx_id, entity, entity_key, as_of_ts, stat, value). No second materialization,
    so the screen, precedents and the model read exactly the row-level point-in-time numbers."""
    parts = []
    for name in names:
        f = cat["features"][name]
        if f.get("kind", "agg") != "agg": continue
        keys = cat["entities"][f["entity"]]
        key_expr = " || '|' || ".join(f"coalesce(tr.{k}::varchar, '')" for k in keys)
        parts.append(f"SELECT x.tx_id, '{f['entity']}' AS entity, {key_expr} AS entity_key, x.tx_ts AS as_of_ts, '{name}' AS stat, x.{name} AS value "
                     f"FROM tx_features x JOIN transactions tr USING(tx_id)")
    con.execute("CREATE OR REPLACE VIEW entity_stats AS " + " UNION ALL ".join(parts)).fetchall()
