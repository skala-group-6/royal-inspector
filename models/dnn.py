"""Reserved plug. Activation condition (docs/MODEL.md): human-reviewed labels >= 10,000 with >= 1,000 positives, or a real-time scoring
requirement. Until then tree models are the right fit for small tabular data. Not in scripts/train.py CANDIDATES."""
class DnnScorer:
    name, version = "dnn", "0"
    def fit(self, X, y, aux=None): raise NotImplementedError("DNN plug is reserved; see docs/MODEL.md activation condition")
    def predict(self, X, aux=None): raise NotImplementedError
    def explain(self, X, aux=None, k=3): raise NotImplementedError
