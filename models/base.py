"""Model socket. Any scorer that implements fit/predict/explain can be plugged into scripts/train.py.
Models are pure over DataFrames: no DB access, no knowledge of rules. `aux` carries rule counts and amount for the baseline only."""
from __future__ import annotations
from typing import Protocol, runtime_checkable
import numpy as np, pandas as pd, joblib

DEMO_DISCLAIMER = ("이 점수는 윤리경영팀 판정이 없는 상태에서 규칙들의 합의로 만든 임시 정답으로 학습한 시연용입니다. "
                   "실제 성능은 판정이 쌓인 뒤 같은 스크립트로 재학습하여 단순 정렬 대비로 측정됩니다.")

@runtime_checkable
class Scorer(Protocol):
    name: str
    version: str
    def fit(self, X: pd.DataFrame, y: pd.Series, aux: pd.DataFrame | None = None) -> "Scorer": ...
    def predict(self, X: pd.DataFrame, aux: pd.DataFrame | None = None) -> np.ndarray: ...
    def explain(self, X: pd.DataFrame, aux: pd.DataFrame | None = None, k: int = 3) -> list[list[tuple[str, float]]]: ...

def topk(contrib: np.ndarray, columns, k: int) -> list[list[tuple[str, float]]]:
    idx = np.argsort(-np.abs(contrib), axis=1)[:, :k]
    return [[(str(columns[j]), float(contrib[i, j])) for j in idx[i]] for i in range(contrib.shape[0])]

def ablation_explain(model, X: pd.DataFrame, medians: pd.Series, k: int = 3) -> list[list[tuple[str, float]]]:
    """Model-agnostic fallback: contribution_j = score(x) − score(x with column j set to its training median). One batch predict per column."""
    base = model.predict(X); out = np.zeros((len(X), X.shape[1]))
    for j, c in enumerate(X.columns):
        Xm = X.copy(); Xm[c] = medians[c]; out[:, j] = base - model.predict(Xm)
    return topk(out, X.columns, k)

def save_model(model, path): joblib.dump(model, path)
def load_model(path): return joblib.load(path)
