"""Step 1: load raw Excel into data/warehouse.duckdb as standard tables.
Re-runnable: drops and recreates everything. Original files are never modified."""
import re, json, sys, os
from pathlib import Path
import pandas as pd, numpy as np, duckdb
sys.path.insert(0, str(Path(__file__).resolve().parent)); from keys import det_ids

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"; DB = Path(os.environ.get("ROYAL_DB", ROOT / "data/warehouse.duckdb")); OUT = ROOT / "data/inventory"
F1 = next(RAW.glob("1.*.xlsx")); F2 = next(RAW.glob("2.*.xlsx"))
report = {}

# ---------- 1. transactions ----------
ex = pd.read_excel(F1, sheet_name="비용점검", header=1)
ex.columns = [c.strip() for c in ex.columns]
won = lambda s: pd.to_numeric(s.astype(str).str.replace(r"[₩,\s]", "", regex=True).replace({"nan": None, "": None}), errors="coerce")
tx = pd.DataFrame({
    "sap_doc_no": ex["SAP전표번호"], "settle_type": ex["정산유형"],
    "account_raw": ex["계정"].astype(str).str.strip(), "mid_account": ex["중계정"],
    "dept": ex["부서"], "emp_id": ex["사번"].astype("Int64"), "emp_name": ex["요청자"],
    "reviewer": ex["검토자"], "approver": ex["승인자"], "approver_id": ex["승인자사번"].astype("Int64"),
    "approval_no": ex["승인번호"].astype("Int64"), "acquirer_no": ex["매입추심번호"],
    "tx_date": pd.to_datetime(ex["거래일"], errors="coerce").dt.date,
    "tx_time": ex["거래시간"].astype(str).where(ex["거래시간"].notna()),
    "created_date": pd.to_datetime(ex["작성일"], errors="coerce").dt.date,
    "approved_date": pd.to_datetime(ex["승인일"], errors="coerce").dt.date,
    "merchant": ex["상호"], "merchant_addr": ex["주소"],
    "project_no": ex["프로젝트번호"], "project_name": ex["프로젝트명"],
    "amount": won(ex["금액"]), "vat": won(ex["부가세"]), "total": won(ex["총금액"]), "prepaid": won(ex["전불정산액"]),
    "cost_center": ex["COSTCENTER"], "memo": ex["적요"],
    "mcc_code": ex["업종코드"].astype("Int64"), "mcc_name": ex["업종명"],
    "has_attachment": ex["첨부파일"].eq("Y"), "is_mobile": ex["모바일구분"].eq("Y"),
    # HR snapshot as of transaction
    "rank": ex["직급"], "title": ex["직위"], "main_dept": ex["주부서"], "weekday": ex["요일"],
    "is_holiday": ex["휴일여부"].eq("Y"), "is_remote": ex["재택여부"].eq("Y"), "is_leave": ex["휴가여부"].eq("Y"),
    "work_start": ex["주간_시작시각"], "work_end": ex["주간_종료시각"], "work_hours": ex["주간_근무시간"],
    "night_start": ex["심야_시작시각"], "night_end": ex["심야_종료시각"], "night_hours": ex["심야_근무시간"],
    "trip_type": ex["출장 종류"],
    "trip_start": pd.to_datetime(ex["출장-시작일"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce").dt.date,
    "trip_end": pd.to_datetime(ex["출장-종료일"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce").dt.date,
    "leave_type": ex["휴가 종류"], "leave_hours": ex["휴가 시간"],
    "home_addr": ex["사용자 주거지 주소"], "approver_addr": ex["승인자 주소"],
    "work_site": ex["주근무지"], "work_site_addr": ex["주근무지 주소"],
})
tx["tx_ts"] = pd.to_datetime(tx["tx_date"].astype(str) + " " + tx["tx_time"].fillna("00:00:00"), errors="coerce")
tx["time_is_dummy"] = tx["tx_time"].isin(["00:00:00", None]) | tx["tx_time"].isna()
# deterministic key: content-derived, independent of row order (docs/STORAGE_ARCHITECTURE.md §5)
tx.insert(0, "tx_id", det_ids(tx, ["sap_doc_no", "acquirer_no", "approval_no", "tx_date", "tx_time", "total", "emp_id"]))
assert tx.tx_id.is_unique, "tx_id collision — key fields insufficient"

# ---------- 2. cancellations ----------
# (a) settle_type '카드취소' = accounting ± pairs -> exclude wholesale
tx["exclude_reason"] = None
tx.loc[tx["settle_type"] == "카드취소", "exclude_reason"] = "accounting_cancel_pair"
# (b) negative 법인카드 rows = partial cancels -> flag and link to the larger positive tx of same emp+merchant
tx["is_partial_cancel"] = (tx["settle_type"] == "법인카드") & (tx["total"] < 0)
tx["cancel_of_tx_id"] = pd.Series([pd.NA] * len(tx), dtype="Int64")
pos = tx[(tx["settle_type"] == "법인카드") & (tx["total"] > 0)]
for i, r in tx[tx["is_partial_cancel"]].iterrows():
    cand = pos[(pos.emp_id == r.emp_id) & (pos.merchant == r.merchant) & (pos.total >= -r.total)]
    if len(cand):
        cand = cand.assign(gap=(pd.to_datetime(cand.tx_date) - pd.to_datetime(r.tx_date)).abs().dt.days).sort_values(["gap", "tx_id"])
        tx.at[i, "cancel_of_tx_id"] = int(cand.iloc[0].tx_id)
tx.loc[tx["is_partial_cancel"], "exclude_reason"] = "partial_cancel_row"
tx["net_total"] = tx["total"]
linked = tx[tx["is_partial_cancel"] & tx["cancel_of_tx_id"].notna()]
for _, r in linked.iterrows():
    tx.loc[tx.tx_id == r.cancel_of_tx_id, "net_total"] += r.total  # r.total is negative
report["cancel"] = dict(accounting_pairs=int((tx.exclude_reason == "accounting_cancel_pair").sum()),
                        partial_cancels=int(tx.is_partial_cancel.sum()), partial_linked=int(len(linked)))

# ---------- 3. policy accounts (merged cells -> forward fill, split names -> join) ----------
rule = pd.read_excel(F1, sheet_name="참고 비용정산지침")
rule.columns = ["account", "description", "dos", "donts", "required_evidence"]
# rows whose 'account' continues a split name: account filled but description empty AND previous row has description
rule["account"] = rule["account"].map(lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else None)
SPLIT_CONT = {"자택방문": "교통비", "현지숙소": "임차관리비"}  # account names that span two rows with their own text
rows, cur = [], None
for _, r in rule.iterrows():
    is_cont = cur is not None and isinstance(r.account, str) and SPLIT_CONT.get(cur["account"]) == r.account
    if is_cont:
        cur["account"] += r.account
    elif isinstance(r.account, str) and pd.notna(r.description):
        cur = dict(account=r.account, description=str(r.description), dos=[], donts=[], required_evidence=[])
        rows.append(cur)
    elif isinstance(r.account, str) and cur is not None and pd.isna(r.description):
        cur["account"] += r.account  # e.g. 자가차량 + 지원비
    if cur is None: continue
    for col in ("description", "dos", "donts", "required_evidence"):
        v = r[col]
        if pd.notna(v) and str(v).strip():
            if col == "description":
                if str(v).strip() not in cur["description"]: cur["description"] += " " + str(v).strip()
            else: cur[col].append(str(v).strip())
pol = pd.DataFrame([{**r, "dos": "\n".join(r["dos"]), "donts": "\n".join(r["donts"]), "required_evidence": "\n".join(r["required_evidence"])} for r in rows])
pol["account"] = pol["account"].str.replace(" ", "")
report["policy_accounts"] = int(len(pol))

# ---------- 4. account map ----------
norm = lambda s: re.sub(r"\s+|\(간접비\)", "", s)
pol_set = set(pol.account)
raw_accounts = sorted(tx.account_raw.unique())
amap = []
for a in raw_accounts:
    n = norm(a); hit = n if n in pol_set else None
    if hit is None:
        for p in pol_set:
            if n.startswith(p) or p.startswith(n): hit = p; break
    amap.append(dict(account_raw=a, account_policy=hit, method="auto" if hit else "unmapped"))
amap = pd.DataFrame(amap)
# manual decisions (one-off, kept in code so reruns reproduce)
manual = {"교육훈련비-기타": "팀별교육비", "복리후생비-기타": "조직관리비", "복리후생비-기타(간접비)": "조직관리비",
          "전사교육비": "팀별교육비", "통신비-기타": "유무선전화료", "전용회선료": "유무선전화료",
          "사용료(CL/AI)": "지급수수료", "SW 사용료": "지급수수료", "조사활동비": "PJT운영비", "산업안전비_소모품비": "소모품비-기타",
          "수입인지세": None, "외국납부세액(국내환급불가)": None}
for k, v in manual.items():
    m = amap.account_raw == k
    if m.any() and amap.loc[m, "account_policy"].isna().all():
        amap.loc[m, ["account_policy", "method"]] = [v, "manual" if v else "no_policy"]
tx = tx.merge(amap[["account_raw", "account_policy"]], on="account_raw", how="left")
report["account_map"] = amap.method.value_counts().to_dict()

# ---------- 5. employees snapshot (mode per emp) ----------
mode = lambda s: s.dropna().mode().iloc[0] if s.dropna().size else None
emp = tx.groupby("emp_id").agg(emp_name=("emp_name", mode), rank=("rank", mode), title=("title", mode), main_dept=("main_dept", mode),
                               home_addr=("home_addr", mode), work_site=("work_site", mode), work_site_addr=("work_site_addr", mode),
                               n_tx=("tx_id", "size"), n_home_variants=("home_addr", "nunique"), n_site_variants=("work_site", "nunique")).reset_index()

# ---------- 6. access logs ----------
ac = pd.read_excel(F2, sheet_name="Sheet1")
acc = pd.DataFrame({"access_ts": pd.to_datetime(ac["출입 일시"]), "weekday": ac["요일"], "gate": ac["장소"],
                    "emp_name": ac["성명"], "emp_id": pd.to_numeric(ac["사원번호"], errors="coerce").astype("Int64"),
                    "dept": ac["부서"], "title": ac["직위"], "event": ac["내용"]})
acc["site"] = acc["gate"].astype(str).str.split("-").str[0]
acc["direction"] = np.select([acc.event.str.contains("입", na=False), acc.event.str.contains("출|퇴", na=False)], ["in", "out"], None)

# ---------- 7. addresses to geocode (placeholder table) ----------
addrs = pd.concat([tx.merchant_addr, tx.home_addr, tx.work_site_addr, tx.approver_addr]).dropna().astype(str).str.strip()
geo = pd.DataFrame({"addr": sorted(addrs.unique())}); geo["lat"] = np.nan; geo["lon"] = np.nan; geo["geocoded_at"] = pd.NaT

# ---------- write ----------
if DB.exists(): DB.unlink()
con = duckdb.connect(str(DB))
for name, df in [("transactions", tx), ("employees", emp), ("access_logs", acc), ("policy_accounts", pol), ("account_map", amap), ("geocode", geo)]:
    con.register("df", df); con.execute(f"CREATE TABLE {name} AS SELECT * FROM df"); con.unregister("df")
con.execute("CREATE VIEW tx_active AS SELECT * FROM transactions WHERE exclude_reason IS NULL")

# ---------- quality report ----------
q = lambda s: con.execute(s).fetchone()[0]
report["rows"] = dict(transactions=q("select count(*) from transactions"), active=q("select count(*) from tx_active"),
                      employees=q("select count(*) from employees"), access_logs=q("select count(*) from access_logs"), addresses=q("select count(*) from geocode"))
report["active_fill_pct"] = {c: round(q(f"select 100.0*count({c})/count(*) from tx_active"), 1) for c in
                             ["merchant_addr", "home_addr", "work_site_addr", "mcc_code", "approval_no", "tx_time", "trip_start", "approver_id"]}
report["active_flags"] = dict(holiday=q("select count(*) from tx_active where is_holiday"), leave=q("select count(*) from tx_active where is_leave"),
                              trip=q("select count(*) from tx_active where trip_type is not null"), attachment=q("select count(*) from tx_active where has_attachment"),
                              dummy_time=q("select count(*) from tx_active where time_is_dummy"), no_policy_account=q("select count(*) from tx_active where account_policy is null"))
report["access_link"] = dict(emp_with_access_pct=round(q("select 100.0*count(*)/(select count(*) from employees) from employees where emp_id in (select distinct emp_id from access_logs)"), 1),
                             tx_with_same_day_access_pct=round(q("""select 100.0*count(distinct t.tx_id)/(select count(*) from tx_active) from tx_active t
                                join access_logs a on a.emp_id=t.emp_id and cast(a.access_ts as date)=t.tx_date"""), 1))
report["employee_consistency"] = dict(multi_home=int((emp.n_home_variants > 1).sum()), multi_site=int((emp.n_site_variants > 1).sum()))
report["unmapped_accounts"] = amap[amap.method != "auto"].to_dict("records")
con.close()
(OUT / "load_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
