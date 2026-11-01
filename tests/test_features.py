import sys, pathlib, os; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import re, pytest, duckdb
from features.executor import load_catalog, build, KEY_COLS
from app import service as s

@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(s.DB))
    if not c.execute("select count(*) from information_schema.tables where table_name='tx_features'").fetchall()[0][0]:
        build(c, quiet=True)
    yield c; c.close()

def test_columns_match_catalog(con):
    cat = load_catalog(); cols = {c for c in con.execute("describe tx_features").df().column_name if c not in KEY_COLS}
    expected = {n for n, f in cat["features"].items() if f.get("kind", "agg") != "history"}
    assert cols == expected

def test_no_rule_columns_and_loader_rejects(con, tmp_path):
    cat = load_catalog(); bad = re.compile(cat["forbidden_name"])
    assert not [c for c in con.execute("describe tx_features").df().column_name if bad.search(c)]
    import yaml; c2 = yaml.safe_load(open(load_catalog.__defaults__[0]))
    c2["features"]["user__all__n_flags"] = {"group": "user", "entity": "user", "window": "all", "agg": "count"}
    p = tmp_path / "bad.yaml"; p.write_text(yaml.safe_dump(c2, allow_unicode=True))
    with pytest.raises(ValueError): load_catalog(p)

def test_n_obs_for_ratios(con):
    cat = load_catalog()
    for n, f in cat["features"].items():
        if f.get("n_obs"):
            assert con.execute(f"select count(*) from tx_features where {n} is not null and coalesce({f['n_obs']},0)=0").fetchall()[0][0] == 0, n

def test_point_in_time_first_tx_and_case17(con):
    first = con.execute("""select count(*) from (select tx_id, row_number() over (partition by emp_id order by tx_ts, tx_id) rn from tx_active) r
                           join tx_features f using(tx_id) where rn=1 and (f.user__all__n_tx<>0 or f.user__all__amount_ratio_median is not null)""").fetchall()[0][0]
    assert first == 0, "earliest tx per employee must have no history"
    rows = con.execute("select f.user_merchant__all__n_tx, f.user__all__since_last_min from transactions t join tx_features f using(tx_id) where t.case_id=17 order by t.tx_ts").fetchall()
    assert rows[0][0] == 0 and rows[1][0] == 1 and rows[1][1] == 12, rows

def test_idempotent_hash(con):
    h = lambda: con.execute("select md5(string_agg(md5(t::varchar), '' order by tx_id)) from tx_features t").fetchall()[0][0]
    h1 = h(); build(con, quiet=True); assert h1 == h()

def test_service_peer_reads_features(con):
    tx = int(con.execute("select tx_id from tx_features where acct_mcc__all__n_tx >= 30 limit 1").fetchall()[0][0])
    p = s.get_context(tx)["peer"]
    assert p and p.get("point_in_time") is True and p["n"] == int(con.execute(f"select acct_mcc__all__n_tx from tx_features where tx_id={tx}").fetchall()[0][0])
