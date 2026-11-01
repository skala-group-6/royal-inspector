"""Gradient-boosted trees plug. XGBoost with per-row feature contributions (pred_contribs). If xgboost cannot be imported on this
machine, falls back to sklearn HistGradientBoostingClassifier (name 'hgb') with ablation explanations so the pipeline never blocks."""
from __future__ import annotations
import numpy as np, pandas as pd
from .base import topk, ablation_explain
try:
    from xgboost import XGBClassifier, DMatrix
    _HAS_XGB = True
except Exception:  # ImportError or missing libomp (OSError)
    _HAS_XGB = False
    from sklearn.ensemble import HistGradientBoostingClassifier

class XgbScorer:
    version = "1"
    def __init__(self, random_state=0):
        self.name = "xgb" if _HAS_XGB else "hgb"
        if _HAS_XGB:
            self.m = XGBClassifier(max_depth=3, n_estimators=200, learning_rate=0.05, min_child_weight=20, subsample=0.9, colsample_bytree=0.9,
                                   random_state=random_state, n_jobs=1, tree_method="hist", eval_metric="aucpr")
        else:
            self.m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=20, random_state=random_state)
    def fit(self, X, y, aux=None):
        self.columns_ = list(X.columns); self.medians_ = X.median(numeric_only=True); self.m.fit(X, y); return self
    def predict(self, X, aux=None): return self.m.predict_proba(X[self.columns_])[:, 1]
    def explain(self, X, aux=None, k=3):
        if _HAS_XGB:
            c = self.m.get_booster().predict(DMatrix(X[self.columns_]), pred_contribs=True)[:, :-1]  # drop bias column
            return topk(np.asarray(c), self.columns_, k)
        return ablation_explain(self, X[self.columns_], self.medians_, k)
