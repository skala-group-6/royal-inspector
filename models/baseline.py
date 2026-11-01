"""Baseline plug: rule-count × log-amount ordering. Reads only `aux` (n_rules, n_violation_rules, total); ignores X.
This is "the way the list is sorted today" expressed in the same socket so it takes the same exam."""
from __future__ import annotations
import numpy as np, pandas as pd

class RuleAmountBaseline:
    name, version = "baseline", "1"
    AUX = ["n_rules", "n_violation_rules", "total"]
    def _raw(self, aux): return (2 * aux["n_violation_rules"].fillna(0) + aux["n_rules"].fillna(0)) * np.log1p(aux["total"].clip(lower=0).fillna(0))
    def fit(self, X, y, aux=None):
        self.raw_max_ = float(max(self._raw(aux).max(), 1e-9)); return self
    def predict(self, X, aux=None):
        return np.clip(self._raw(aux).to_numpy(dtype=float) / self.raw_max_, 0, 1)
    def explain(self, X, aux=None, k=3):
        lt = np.log1p(aux["total"].clip(lower=0).fillna(0)).to_numpy(); nv = aux["n_violation_rules"].fillna(0).to_numpy(); nr = aux["n_rules"].fillna(0).to_numpy()
        return [[("n_violation_rules", float(2 * nv[i] * lt[i] / self.raw_max_)), ("n_rules", float(nr[i] * lt[i] / self.raw_max_)), ("total", float(lt[i] / self.raw_max_))] for i in range(len(aux))]
