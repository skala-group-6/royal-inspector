"""Logistic-regression plug (simple baseline model). Pipeline: median imputation → standardization → L2 logistic, class_weight balanced."""
from __future__ import annotations
import numpy as np, pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from .base import topk

class LogisticScorer:
    name, version = "logistic", "1"
    def __init__(self, random_state=0):
        self.pipe = Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler()), ("lr", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=random_state))])
    def fit(self, X, y, aux=None):
        self.columns_ = list(X.columns); self.pipe.fit(X, y); return self
    def predict(self, X, aux=None): return self.pipe.predict_proba(X[self.columns_])[:, 1]
    def explain(self, X, aux=None, k=3):
        Z = self.pipe[:-1].transform(X[self.columns_]); contrib = Z * self.pipe[-1].coef_[0]
        return topk(np.asarray(contrib), self.columns_, k)
