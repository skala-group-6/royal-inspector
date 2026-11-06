"""db/schema.sql must apply cleanly on Postgres 17 and keep its guards. Uses Docker (postgres:17-alpine); skipped when Docker is unavailable."""
import shutil, subprocess, time, uuid
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("docker") is None or subprocess.run(["docker", "info"], capture_output=True).returncode != 0, reason="docker not available")

@pytest.fixture(scope="module")
def pg():
    name = f"ri_schema_{uuid.uuid4().hex[:6]}"
    subprocess.run(["docker", "run", "--rm", "-d", "--name", name, "-e", "POSTGRES_PASSWORD=x", "-e", "POSTGRES_DB=t", "-v", f"{ROOT / 'db'}:/db:ro", "postgres:17-alpine"], check=True, capture_output=True)
    try:
        for _ in range(60):
            if subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres"], capture_output=True).returncode == 0: break
            time.sleep(1)
        def psql(sql=None, file=None):
            cmd = ["docker", "exec", "-i", name, "psql", "-U", "postgres", "-d", "t", "-v", "ON_ERROR_STOP=1", "-tA"] + (["-f", file] if file else [])
            return subprocess.run(cmd, input=sql, capture_output=True, text=True)
        yield psql
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)

def test_schema_applies(pg):
    r = pg(file="/db/schema.sql"); assert r.returncode == 0, r.stderr
    n = pg("select count(*) from information_schema.tables where table_schema='ri' and table_type='BASE TABLE'").stdout.strip()
    assert int(n) == 25

def test_guards_and_views(pg):
    seed = """set search_path to ri;
      insert into tenants(name) values ('t1'); insert into reviewers(tenant_id,name,role,counts_as_label) values (1,'dev','dev',false);
      insert into data_sources(tenant_id,kind,name) values (1,'card_tx','x'); insert into loads(tenant_id,source_id,file_hash) values (1,1,'h');
      insert into transactions(tenant_id,tx_id,load_id,tx_ts,tx_date,total) values (1,-1,1,'2025-03-10 22:56+09','2025-03-10',1000);
      select set_config('ri.tenant_id','1',false);
      insert into model_versions(tenant_id,model_version,model_id,plug,label_source) values (1,'v1','m','models.x','weak');
      insert into model_bindings(tenant_id,role,model_version,state,set_by) values (1,'rank','v1','shadow','a'),(1,'rank','v1','serving','a');
      insert into reviews(tenant_id,review_id,tx_id,decision,reviewer_id) values (1,'r1',-1,'ok',1);
      select (select count(*) from tx_active)||','||(select state from current_bindings where role='rank')||','||(select decision from latest_reviews);"""
    r = pg(seed); assert r.returncode == 0, r.stderr; assert r.stdout.strip().endswith("1,serving,ok")
    assert "violates foreign key" in pg("set search_path to ri; insert into reviews(tenant_id,review_id,tx_id,decision,reviewer_id) values (1,'r2',999,'ok',1)").stderr
    assert "violates check" in pg("set search_path to ri; insert into model_bindings(tenant_id,role,model_version,state,set_by) values (1,'rank','v1','live','a')").stderr
