"""Feature executor: turns the pack features catalog into one SQL statement and materializes tx_features on PostgreSQL.
Point-in-time by construction: window frames end at INTERVAL '1 microsecond' PRECEDING (self and simultaneous rows excluded);
correlated / LATERAL forms use h.tx_ts < t.tx_ts. Both strategies must agree (validated by scripts/validate_features.py).
Grain (features.yaml): tx = this transaction's instant (default); day = yesterday's baseline (h.tx_date < t.tx_date), computed once
per (entity, window, as_of_date) into a baseline table and joined by tx_date — this is what keeps large groups (rank, dept) O(n).
Aggregates PostgreSQL cannot run as window functions (quantiles, count(distinct), percentile-of-value, focal-row predicates)
are computed in one LATERAL subquery per (entity, window) over an indexed temp copy of the source."""
from __future__ import annotations
import re
from pathlib import Path
import yaml

import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); import paths
from db import conn as C
CATALOG = paths.FEATURES_CATALOG
KEY_COLS = ["tx_id", "tx_ts", "tx_date", "emp_id", "is_synthetic"]
BASE = "feat_base"                     # temp table; `h` in every correlated/LATERAL form
LATERAL_AGGS = ("quantile", "ratio_to_quantile", "count_distinct", "percentile_of_value")
BASELINE_AGGS = ("count", "sum", "quantile", "ratio_to_quantile", "count_distinct", "ratio_predicate")  # day grain, value independent of the focal row
PIT_MARKERS = ("INTERVAL '1 microsecond' PRECEDING", "h.tx_ts < t.tx_ts", "h.tx_date < t.tx_date", "ft.tx_ts < t.tx_ts")
GRAINS = ("tx", "day")

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
            g = f.setdefault("grain", "tx")
            if g not in GRAINS: raise ValueError(f"{name}: grain must be one of {GRAINS}")
            if g == "day" and (wins[f["window"]].get("kind") == "calendar_day" or f["agg"] in ("since_last_minutes", "until_next_minutes")):
                raise ValueError(f"{name}: grain day is only for prior-window aggregates")
            if f.get("n_obs") and feats[f["n_obs"]].get("grain", "tx") != g: raise ValueError(f"{name}: n_obs {f['n_obs']} must have the same grain")
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
def _filter(f): return f" FILTER (WHERE {f['where']})" if f.get("where") else ""
def _round(expr): return f"round(({expr})::numeric, 6)::float8"
def _h(col): return f"h.{col}" if col.isidentifier() else col   # expressions such as sigungu_of(merchant_addr) resolve to h inside the subquery
def _minutes(a, b): return f"(extract(epoch from date_trunc('minute', {b})) - extract(epoch from date_trunc('minute', {a}))) / 60"  # minute boundaries crossed

def _frame(cat, f):
    w = cat["windows"][f["window"]]
    lo = "UNBOUNDED PRECEDING" if w.get("lo") is None else f"{w['lo']} PRECEDING"
    return f"RANGE BETWEEN {lo} AND INTERVAL '1 microsecond' PRECEDING"

def _over(cat, f): return f"OVER (PARTITION BY {', '.join(_keys(cat, f))} ORDER BY tx_ts {_frame(cat, f)})"
def _over_day(cat, f): return f"OVER (PARTITION BY {', '.join(_keys(cat, f))}, tx_date)"

def _cutoff(f, focal="t", date_col="tx_date"):
    """Point-in-time boundary: tx grain = strictly before this instant; day grain = strictly before this date (yesterday's baseline)."""
    return f"h.tx_date < {focal}.{date_col}" if f.get("grain", "tx") == "day" else f"h.tx_ts < {focal}.tx_ts"

def _lateral_cond(cat, f, focal="t", date_col="tx_date"):
    """Rows of `h` that count for focal row `focal` (t = a transaction, d = a (key, as_of_date) baseline row)."""
    keys, w = _keys(cat, f), cat["windows"][f["window"]]
    cond = " AND ".join(f"h.{k} = {focal}.{k}" for k in keys)
    if w.get("kind") == "calendar_day": return cond + f" AND h.tx_date = {focal}.tx_date"      # same day, self included (lookahead)
    cond += " AND " + _cutoff(f, focal, date_col)
    if w.get("lo"):
        cond += f" AND h.tx_date >= {focal}.{date_col} - {w['lo']}" if f.get("grain", "tx") == "day" else f" AND h.tx_ts >= {focal}.tx_ts - {w['lo']}"
    return cond

def baseline_column(cat, name, f, bl: dict) -> str:
    """Register this day-grain feature's statistic in the (entity, window) baseline table and return the outer expression."""
    agg, of = f["agg"], f.get("of", "total")
    key = (f["entity"], f["window"]); alias = f"b_{f['entity']}_{f['window']}"
    b = bl.setdefault(key, {"alias": alias, "table": f"bl_{f['entity']}_{f['window']}", "keys": _keys(cat, f), "entity": f["entity"], "window": f["window"],
                            "cond": _lateral_cond(cat, f, focal="d", date_col="as_of_date"), "cols": {}, "n_obs": None})
    if agg == "count":
        b["cols"][name] = f"count({_where_case(f, 'h.tx_id')})"; b["n_obs"] = name; return f"{alias}.{name}"
    if agg == "sum": b["cols"][name] = f"sum({_h(of)}){_filter(f)}"
    elif agg in ("quantile", "ratio_to_quantile"):
        b["cols"][name] = f"percentile_cont({f['p']}) WITHIN GROUP (ORDER BY {_h(of)}){_filter(f)}"
        if agg == "ratio_to_quantile": return f"t.{of} / nullif({alias}.{name}, 0)"
    elif agg == "count_distinct": b["cols"][name] = f"count(DISTINCT {_h(of)}){_filter(f)}"
    elif agg == "ratio_predicate": b["cols"][name] = f"avg(CASE WHEN {f['predicate']} THEN 1 ELSE 0 END){_filter(f)}"
    else: raise ValueError(f"{name}: {agg} is not a baseline aggregate")
    return f"{alias}.{name}"

def lateral_column(cat, name, f, lat: dict) -> str:
    """Register this feature's aggregate in the (entity, window) LATERAL and return the outer expression."""
    agg, of = f["agg"], f.get("of", "total")
    key = (f["entity"], f["window"]); alias = f"l_{f['entity']}_{f['window']}"
    aggs = lat.setdefault(key, {"alias": alias, "cond": _lateral_cond(cat, f), "cols": {}})["cols"]
    if agg in ("quantile", "ratio_to_quantile"):
        aggs[name] = f"percentile_cont({f['p']}) WITHIN GROUP (ORDER BY {_h(of)}){_filter(f)}"
        return f"t.{of} / nullif({alias}.{name}, 0)" if agg == "ratio_to_quantile" else f"{alias}.{name}"
    if agg == "count_distinct": aggs[name] = f"count(DISTINCT {_h(of)}){_filter(f)}"
    elif agg == "percentile_of_value":
        w = f" AND ({f['where']})" if f.get("where") else ""
        aggs[name] = f"100.0 * count(*) FILTER (WHERE {_h(of)} < t.{of}{w}) / nullif(count(*){_filter(f)}, 0)"
    elif agg == "ratio_predicate": aggs[name] = f"avg(CASE WHEN {f['predicate']} THEN 1 ELSE 0 END){_filter(f)}"
    else: raise ValueError(f"{name}: {agg} is not a LATERAL aggregate")
    return f"{alias}.{name}"

def render_window(cat, name, f, lat: dict | None = None, bl: dict | None = None) -> str:
    """Window strategy. Day grain → baseline table (bl) or LATERAL with a date cutoff; aggregates PG cannot window → LATERAL (lat).
    Without a context (lat/bl None) fall back to the correlated form, which carries the same PIT marker."""
    agg, keys = f["agg"], _keys(cat, f)
    of = f.get("of", "total")
    same_day = cat["windows"][f["window"]].get("kind") == "calendar_day"
    focal_dependent = agg == "percentile_of_value" or (agg == "ratio_predicate" and "t." in f["predicate"])
    if f.get("grain", "tx") == "day" and agg in BASELINE_AGGS and not focal_dependent:
        if bl is None: return render_correlated(cat, name, f)
        return _round(_null_guard(keys, baseline_column(cat, name, f, bl)))
    if agg in LATERAL_AGGS or focal_dependent or f.get("grain", "tx") == "day":
        if lat is None: return render_correlated(cat, name, f)
        return _round(_null_guard(keys, lateral_column(cat, name, f, lat)))
    if agg == "count":
        if same_day: e = f"count({_where_case(f)}) {_over_day(cat, f)} - ({_where_case(f, '1')} IS NOT NULL)::int"
        else: e = f"count({_where_case(f)}) {_over(cat, f)}"
    elif agg == "sum": e = f"sum({_where_case(f, of)}) {_over(cat, f)}"
    elif agg == "ratio_predicate":
        flag = f"(CASE WHEN {f['predicate']} THEN 1 ELSE 0 END)"
        e = f"avg({_where_case(f, flag)}) {_over(cat, f)}"
    elif agg == "since_last_minutes":
        prev = f"(SELECT max(h.tx_ts) FROM {BASE} h WHERE {' AND '.join(f'h.{k} = t.{k}' for k in keys)} AND h.tx_ts < t.tx_ts AND NOT h.time_is_dummy)"
        e = f"CASE WHEN t.time_is_dummy THEN NULL ELSE {_minutes(prev, 't.tx_ts')} END"
    elif agg == "until_next_minutes":
        nxt = f"lead(tx_ts) OVER (PARTITION BY {', '.join(keys)} ORDER BY tx_ts, tx_id)"
        e = f"CASE WHEN t.time_is_dummy THEN NULL ELSE {_minutes('t.tx_ts', nxt)} END"
    else: raise ValueError(f"{name}: unsupported agg {agg}")
    return _round(_null_guard(keys, e))

def render_correlated(cat, name, f) -> str:
    """Independent check path: one plain correlated subquery per feature (slow; validation runs it on a sample)."""
    agg, keys, of = f["agg"], _keys(cat, f), f.get("of", "total")
    w = cat["windows"][f["window"]]
    if w.get("kind") == "calendar_day" and agg == "count": return render_window(cat, name, f)   # same-day count stays on the window path (lookahead)
    cond = _lateral_cond(cat, f)
    if f.get("where"): cond += f" AND ({f['where']})"
    sub = lambda sel: f"(SELECT {sel} FROM {BASE} h WHERE {cond})"
    if agg == "count": e = sub("count(*)")
    elif agg == "sum": e = sub(f"sum(h.{of})")
    elif agg == "quantile": e = sub(f"percentile_cont({f['p']}) WITHIN GROUP (ORDER BY {_h(of)})")
    elif agg == "ratio_to_quantile": e = f"t.{of} / nullif({sub(f'percentile_cont({f[chr(112)]}) WITHIN GROUP (ORDER BY {_h(of)})')}, 0)"
    elif agg == "ratio_predicate": e = sub(f"avg(CASE WHEN {f['predicate']} THEN 1 ELSE 0 END)")
    elif agg == "count_distinct": e = sub(f"count(DISTINCT {_h(of)})")
    elif agg == "percentile_of_value": e = sub(f"100.0 * count(*) FILTER (WHERE {_h(of)} < t.{of}) / nullif(count(*), 0)")
    elif agg in ("since_last_minutes", "until_next_minutes"): return render_window(cat, name, f)  # since_last is already correlated; until_next is lookahead
    else: raise ValueError(f"{name}: unsupported agg {agg}")
    return _round(_null_guard(keys, e))

def render_history(name, f) -> str:
    # only built with with_history=True; counts prior flagged tx (latest rule run) of the same employee
    return "(SELECT count(DISTINCT fl.tx_id) FROM current_flags fl JOIN transactions ft ON ft.tenant_id = tenant() AND ft.tx_id = fl.tx_id WHERE ft.emp_id = t.emp_id AND ft.tx_ts < t.tx_ts)"

def render_feature(cat, name, f, strategy="window", with_history=False):
    kind = f.get("kind", "agg")
    if kind == "history": return render_history(name, f) if with_history else None
    if kind == "column": return f["expr"]
    return render_window(cat, name, f) if strategy == "window" else render_correlated(cat, name, f)

def _laterals(cat) -> dict:
    """(entity, window) pairs that render as per-row LATERALs under the window strategy (without building SQL)."""
    lat = {}
    for name, f in cat["features"].items():
        if f.get("kind", "agg") == "agg": render_window(cat, name, f, lat, {})
    return lat

def build_sql(cat, strategy="window", with_history=False, target="tx_features", focal_ids=None) -> tuple[str, list[str], dict]:
    """Returns (CTAS sql, feature names, baseline specs). Baseline temp tables must exist before the CTAS runs (build_baselines)."""
    cols, names, lat, bl = [], [], {}, {}
    for name, f in cat["features"].items():
        kind = f.get("kind", "agg")
        if kind == "history":
            if not with_history: continue
            e = render_history(name, f)
        elif kind == "column": e = f["expr"] if "::int" in f["expr"] else _round(f["expr"])
        else: e = render_window(cat, name, f, lat, bl) if strategy == "window" else render_correlated(cat, name, f)
        if kind != "column" and not f.get("lookahead"):
            pit = any(m in e for m in PIT_MARKERS) \
                or any(f"{l['alias']}." in e and (("h.tx_ts < t.tx_ts" in l["cond"]) or ("h.tx_date < t.tx_date" in l["cond"])) for l in lat.values()) \
                or any(f"{b['alias']}." in e and "h.tx_date < d.as_of_date" in b["cond"] for b in bl.values())
            if not pit: raise AssertionError(f"{name}: rendered SQL is not point-in-time: {e[:120]}")
        cols.append(f"{e} AS {name}"); names.append(name)
    joins = "".join(f"\nLEFT JOIN LATERAL (SELECT {', '.join(f'{sql} AS {n}' for n, sql in l['cols'].items())} FROM {BASE} h WHERE {l['cond']}) {l['alias']} ON true" for l in lat.values())
    joins += "".join(f"\nLEFT JOIN {b['table']} {b['alias']} ON {' AND '.join(f'{b[chr(97)+chr(108)+chr(105)+chr(97)+chr(115)]}.{k} = t.{k}' for k in b['keys'])} AND {b['alias']}.as_of_date = t.tx_date" for b in bl.values())
    focal = f" WHERE t.tx_id IN ({','.join(str(int(i)) for i in focal_ids)})" if focal_ids else ""
    sql = f"""CREATE TABLE {target} AS
SELECT t.tenant_id, {cat['version']}::int AS features_version, {', '.join('t.' + k for k in KEY_COLS)}, {', '.join(cols)}
FROM {BASE} t{joins}{focal} ORDER BY t.tx_id"""
    return sql, names, bl

def indexes(cat) -> list[list[str]]:
    """One (keys, tx_ts) and one (keys, tx_date) index per catalog entity: tx-grain forms range on tx_ts, day-grain forms on tx_date."""
    out = []
    for keys in cat["entities"].values():
        out += [keys + ["tx_ts"], keys + ["tx_date"]]
    return out

def cluster_keys(con, source, cat, lat: dict) -> list[str]:
    """Physical order for the base copy: keys of the per-row LATERAL entity with the largest group. Its range scans then touch
    few heap blocks (measured 5x on the acct_mcc percentile). Values do not depend on this; only speed does."""
    best, best_n = [], 0
    for (entity, _w) in lat:
        keys = cat["entities"][entity]
        n = C.one(con, f"select coalesce(max(c), 0) from (select count(*) c from {source} group by {', '.join(keys)}) g")
        if n > best_n: best, best_n = keys, n
    return best

def prepare_base(con, source, cat, order: list[str] = ()):
    """Indexed temp copy of the source view; every window/LATERAL/correlated form reads it as `h`."""
    con.execute(f"DROP TABLE IF EXISTS {BASE}")
    con.execute(f"CREATE TEMP TABLE {BASE} AS SELECT * FROM {source}" + (f" ORDER BY {', '.join(order)}, tx_date" if order else ""))
    for cols in indexes(cat): con.execute(f"CREATE INDEX ON {BASE} ({', '.join(cols)})")
    con.execute(f"ANALYZE {BASE}")

def build_baselines(con, cat, bl: dict):
    """One GROUP BY per (entity, window): every (key, date) pair that occurs, LEFT JOIN its prior rows (h.tx_date < d.as_of_date) → counts 0 / quantiles NULL when there is no history."""
    for b in bl.values():
        keys = ", ".join(b["keys"]); dkeys = ", ".join(f"d.{k}" for k in b["keys"])
        con.execute(f"DROP TABLE IF EXISTS {b['table']}")
        con.execute(f"""CREATE TEMP TABLE {b['table']} AS
SELECT {dkeys}, d.as_of_date, {', '.join(f'{sql} AS {n}' for n, sql in b['cols'].items())}
FROM (SELECT DISTINCT {keys}, tx_date AS as_of_date FROM {BASE} WHERE {' AND '.join(f'{k} IS NOT NULL' for k in b['keys'])}) d
LEFT JOIN {BASE} h ON {b['cond']}
GROUP BY {dkeys}, d.as_of_date""")
        con.execute(f"CREATE INDEX ON {b['table']} ({keys}, as_of_date)"); con.execute(f"ANALYZE {b['table']}")

def write_entity_baselines(con, cat, bl: dict):
    """Persist the baselines in long form (entity_baselines) so the screen and precedents read the same numbers the model saw."""
    v = int(cat["version"])
    con.execute("DELETE FROM entity_baselines WHERE tenant_id = tenant() AND features_version = %s", [v])
    for b in bl.values():
        key_expr = " || '|' || ".join(f"coalesce({k}::text, '')" for k in b["keys"])
        n_obs = b["n_obs"] or "NULL"
        for name in b["cols"]:
            con.execute(f"INSERT INTO entity_baselines(tenant_id, features_version, entity, \"window\", entity_key, as_of_date, stat, value, n_obs) "
                        f"SELECT tenant(), {v}, '{b['entity']}', '{b['window']}', {key_expr}, as_of_date, '{name}', {name}::float8, {n_obs} FROM {b['table']}")

def table_hash(con, target):
    return C.one(con, f"select md5(string_agg(md5(t::text), '' order by tx_id)) from {target} t")

def build(con, strategy="window", with_history=False, source=None, target="tx_features", quiet=False, focal_ids=None) -> dict:
    cat = load_catalog()
    sql, names, bl = build_sql(cat, strategy, with_history, target, focal_ids)
    source = source or cat["source"]
    prepare_base(con, source, cat, cluster_keys(con, source, cat, _laterals(cat)))
    build_baselines(con, cat, bl)
    if target == "tx_features": con.execute("DROP VIEW IF EXISTS entity_stats")
    con.execute(f"DROP TABLE IF EXISTS {target}")
    con.execute(sql)
    n = C.one(con, f"select count(*) from {target}"); h = table_hash(con, target)
    if target == "tx_features": write_entity_baselines(con, cat, bl); create_entity_stats_view(con, cat, names)
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
        key_expr = " || '|' || ".join(f"coalesce(tr.{k}::text, '')" for k in keys)
        parts.append(f"SELECT x.tx_id, '{f['entity']}' AS entity, {key_expr} AS entity_key, x.tx_ts AS as_of_ts, '{name}' AS stat, x.{name} AS value "
                     f"FROM tx_features x JOIN transactions tr ON tr.tenant_id = x.tenant_id AND tr.tx_id = x.tx_id")
    con.execute("CREATE VIEW entity_stats AS " + " UNION ALL ".join(parts))
