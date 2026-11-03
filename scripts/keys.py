"""Deterministic transaction keys. tx_id must come from the transaction's own content, never from row order,
so a verdict stored elsewhere (Postgres) keeps pointing at the same transaction when the Excel is re-exported."""
import hashlib
import pandas as pd

def _norm(v) -> str:
    if v is None or (isinstance(v, float) and v != v) or v is pd.NA or v is pd.NaT: return ""
    if isinstance(v, float): return str(int(round(v)))
    return str(v)

def det_ids(df: pd.DataFrame, cols: list[str], prefix: str = "") -> pd.Series:
    """Signed 63-bit int per row: sha1(prefix|col1|...|colN|occ). occ = position among rows with an identical tuple,
    so exact duplicates get distinct ids and the id *set* is independent of file order. Caller must assert uniqueness."""
    key = pd.Series(["|".join(_norm(v) for v in row) for row in df[cols].itertuples(index=False)], index=df.index)
    occ = key.groupby(key).cumcount().astype(str)
    return (prefix + key + "|" + occ).map(lambda s: int.from_bytes(hashlib.sha1(s.encode()).digest()[:8], "big", signed=True)).astype("int64")

def det_id(*parts) -> int:
    return int.from_bytes(hashlib.sha1("|".join(_norm(p) for p in parts).encode()).digest()[:8], "big", signed=True)
