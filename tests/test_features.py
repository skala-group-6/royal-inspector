import sys, pathlib, os; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import re, pytest
from db import conn as C
from features.executor import load_catalog, build, table_hash, KEY_COLS

META = set(KEY_COLS) | {"tenant_id", "features_version"}

@pytest.fixture(scope="module")
def con(pgdb):
    c = C.connect()
    if not C.table_exists(c, "tx_features"): build(c, quiet=True)
    yield c; c.close()

def test_columns_match_catalog(con):
    cat = load_catalog(); cols = {c for c in C.columns(con, "tx_features") if c not in META}
    expected = {n for n, f in cat["features"].items() if f.get("kind", "agg") != "history"}
    assert cols == expected

def test_no_rule_columns_and_loader_rejects(con, tmp_path):
    cat = load_catalog(); bad = re.compile(cat["forbidden_name"])
    assert not [c for c in C.columns(con, "tx_features") if bad.search(c)]
    import yaml; c2 = yaml.safe_load(open(load_catalog.__defaults__[0]))
    c2["features"]["user__all__n_flags"] = {"group": "user", "entity": "user", "window": "all", "agg": "count"}
    p = tmp_path / "bad.yaml"; p.write_text(yaml.safe_dump(c2, allow_unicode=True))
    with pytest.raises(ValueError): load_catalog(p)

def test_n_obs_for_ratios(con):
    cat = load_catalog()
    for n, f in cat["features"].items():
        if f.get("n_obs"):
            assert C.one(con, f"select count(*) from tx_features where {n} is not null and coalesce({f['n_obs']},0)=0") == 0, n

def test_point_in_time_first_tx_and_case17(con):
    first = C.one(con, """select count(*) from (select tx_id, row_number() over (partition by emp_id order by tx_ts, tx_id) rn from tx_active) r
                          join tx_features f using(tx_id) where rn=1 and (f.user__all__n_tx<>0 or f.user__all__amount_ratio_median is not null)""")
    assert first == 0, "earliest tx per employee must have no history"
    rows = C.q(con, "select f.user_merchant__all__n_tx, f.user__all__since_last_min from transactions t join tx_features f on f.tenant_id=t.tenant_id and f.tx_id=t.tx_id where t.tenant_id=tenant() and t.case_id=17 order by t.tx_ts").values.tolist()
    assert rows[0][0] == 0 and rows[1][0] == 1 and rows[1][1] == 12, rows

def test_day_grain_is_constant_within_a_day(con):
    """rank is day grain: every transaction of one rank on one date sees the same baseline (yesterday's), whatever its time of day."""
    assert C.one(con, """select count(*) from (select t.rank, t.tx_date, count(distinct f.rank__all__n_tx) k
                          from tx_features f join tx_active t on t.tx_id=f.tx_id where t.rank is not null group by 1,2) s where k > 1""") == 0

def test_idempotent_hash(con):
    h1 = table_hash(con, "tx_features"); build(con, quiet=True); assert h1 == table_hash(con, "tx_features")

def test_service_peer_reads_features(con):
    from app import service as s
    tx = int(C.one(con, "select tx_id from tx_features where acct_mcc__all__n_tx >= 30 order by tx_id limit 1"))
    p = s.get_context(tx)["peer"]
    assert p and p.get("point_in_time") is True and p["n"] == int(C.one(con, f"select acct_mcc__all__n_tx from tx_features where tx_id={tx}"))
