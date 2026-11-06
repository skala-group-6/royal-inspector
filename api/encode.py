"""JSON-safe encoding of service outputs. tx ids are 64-bit content hashes and exceed JavaScript's safe integer range (2^53),
so every id field is written as a string (docs/API.md principle 5). DataFrames → records, numpy/pandas scalars → python, NaN/NaT → None."""
import math, datetime as dt
import numpy as np, pandas as pd

ID_KEYS = {"tx_id", "cancel_of_tx_id", "after"}

def clean(o, key=None):
    if key in ID_KEYS and o is not None and not (isinstance(o, float) and math.isnan(o)): return str(int(o))
    if key == "related_tx_ids" and o is not None: return [str(int(x)) for x in o]
    if isinstance(o, pd.DataFrame): return [clean(r) for r in o.to_dict(orient="records")]
    if isinstance(o, dict): return {str(k): clean(v, k) for k, v in o.items()}
    if isinstance(o, (list, tuple, np.ndarray)): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return None if math.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if o is pd.NaT or o is None: return None
    if isinstance(o, (pd.Timestamp, dt.datetime)): return o.isoformat(timespec="seconds")
    if isinstance(o, dt.date): return o.isoformat()
    if isinstance(o, dt.time): return o.isoformat()
    try:
        if pd.isna(o): return None
    except (TypeError, ValueError): pass
    return o
