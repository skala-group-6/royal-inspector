"""Step 2: column profiling + key matching. Writes data/inventory/profile_*.csv. No raw PII printed."""
import pandas as pd, numpy as np, re
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import paths
OUT = paths.ROOT / "data/inventory"
F1 = next(paths.RAW_DIR.glob(paths.RAW_GLOB[0])); F2 = next(paths.RAW_DIR.glob(paths.RAW_GLOB[1]))
PII = {"요청자","검토자","승인자","사용자 주거지 주소","승인자 주소","성명","주소","주근무지 주소"}

ex = pd.read_excel(F1, sheet_name="비용점검", header=1)
ac = pd.read_excel(F2, sheet_name="Sheet1", header=0)
print("loaded", ex.shape, ac.shape)

def profile(df, name):
    rows=[]
    for c in df.columns:
        s=df[c]; nn=s.notna() & (s.astype(str).str.strip()!="")
        top = "" if c in PII else " / ".join(f"{k}({v})" for k,v in s[nn].astype(str).value_counts().head(4).items())
        rows.append(dict(col=c, dtype=str(s.dtype), fill_pct=round(nn.mean()*100,1), n_unique=int(s[nn].nunique()), top_values=top[:120],
                         sample_len=int(s[nn].astype(str).str.len().median()) if nn.any() else 0))
    p=pd.DataFrame(rows); p.to_csv(OUT/f"profile_{name}.csv", index=False)
    print(f"\n== {name} ==\n", p[["col","dtype","fill_pct","n_unique","top_values"]].to_string(index=False, max_colwidth=70))
    return p
pe=profile(ex,"expense"); pa=profile(ac,"access")

print("\n== 날짜/금액/취소 ==")
d=pd.to_datetime(ex["거래일"], errors="coerce"); print("거래일 범위:", d.min(), "~", d.max(), "| 월별 건수:", d.dt.to_period("M").value_counts().sort_index().to_dict())
amt=pd.to_numeric(ex["총금액"], errors="coerce"); print("총금액: 음수", (amt<0).sum(), "건 / 0원", (amt==0).sum(), "/ 중앙값", amt.median(), "/ 최대", amt.max())
neg=ex[amt<0]; pos=ex[amt>0]
k=["사번","상호"]; m=neg.assign(a=-amt[amt<0]).merge(pos.assign(a=amt[amt>0])[k+["a"]], on=k+["a"], how="left", indicator=True)
print("취소건 중 (사번,상호,금액) 짝 있는 비율:", round((m["_merge"]=="both").mean()*100,1), "%")
print("휴일여부:", ex["휴일여부"].value_counts(dropna=False).to_dict()); print("휴가여부:", ex["휴가여부"].value_counts(dropna=False).to_dict()); print("재택여부:", ex["재택여부"].value_counts(dropna=False).to_dict())
print("출장 종류:", ex["출장 종류"].value_counts(dropna=False).head(6).to_dict())
print("첨부파일 채움:", round(ex["첨부파일"].notna().mean()*100,1), "% | 참석자 채움:", round(ex["참석자"].notna().mean()*100,1), "%")
print("사용자 수:", ex["사번"].nunique(), "| 부서 수:", ex["부서"].nunique(), "| 계정 수:", ex["계정"].nunique(), "| 업종코드 수:", ex["업종코드"].nunique(), "| 상호 수:", ex["상호"].nunique())
print("거래시간 샘플 형식:", ex["거래시간"].dropna().astype(str).head(3).tolist())
print("주소 형식 길이 중앙값(가맹점):", ex["주소"].dropna().astype(str).str.len().median(), "| 주거지:", ex["사용자 주거지 주소"].dropna().astype(str).str.len().median())
print("주거지 주소 토큰 수(공백 기준) 분포:", ex["사용자 주거지 주소"].dropna().astype(str).str.split().str.len().value_counts().head(5).to_dict())

print("\n== 규정표 계정 vs 거래 계정 ==")
rule=pd.read_excel(F1, sheet_name="참고 비용정산지침", header=0)
ra=set(rule["계정"].dropna().astype(str).str.strip()); ea=set(ex["계정"].dropna().astype(str).str.strip())
print("거래 계정 수", len(ea), "| 규정표 계정 수", len(ra), "| 거래 계정 중 규정표에 없는 것:", sorted(ea-ra)[:30])

print("\n== 출입기록 키 매칭 ==")
ad=pd.to_datetime(ac["출입 일시"], errors="coerce"); print("출입 기간:", ad.min(), "~", ad.max(), "| 사원 수:", ac["사원번호"].nunique(), "| 장소:", ac["장소"].value_counts().head(5).to_dict())
print("사번 형식 예(거래/출입, 마스킹):", re.sub(r"\d","9",str(ex["사번"].dropna().iloc[0])), re.sub(r"\d","9",str(ac["사원번호"].dropna().iloc[0])))
e_ids=set(ex["사번"].dropna().astype(str).str.strip()); a_ids=set(ac["사원번호"].dropna().astype(str).str.strip())
print(f"거래 사용자 {len(e_ids)}명 중 출입기록에 있는 사람: {len(e_ids&a_ids)}명 ({round(len(e_ids&a_ids)/len(e_ids)*100,1)}%)")
print("거래 건 기준 출입기록 보유자 비율:", round(ex["사번"].astype(str).str.strip().isin(a_ids).mean()*100,1), "%")
print("출입 '내용' 값:", ac["내용"].value_counts().head(6).to_dict())

print("\n== 시나리오 흔적 ==")
print("같은 사번, 같은 날, 주유 업종 2회 이상:", ex[ex["업종명"].astype(str).str.contains("주유", na=False)].groupby(["사번","거래일"]).size().ge(2).sum(), "건")
print("휴일 거래:", (ex["휴일여부"].astype(str).str.upper().isin(["Y","TRUE","1","휴일"])).sum(), "| 첨부파일 없는 거래:", ex["첨부파일"].isna().sum())
print("같은 첨부파일명 2건 이상 중복:", (ex["첨부파일"].dropna().value_counts()>1).sum(), "개 파일")
print("동일 사번·상호·거래일 2건 이상(분할 후보):", ex.groupby(["사번","상호","거래일"]).size().ge(2).sum(), "그룹")
