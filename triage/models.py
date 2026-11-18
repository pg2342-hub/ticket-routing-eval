"""Routers return one answer per ticket in the same shape as a Jev Choice answer:

    {"type": "choice", "choice": "feature-flags", "confidence": 0.91,
     "probabilities": {"feature-flags": 0.93, "experiments": 0.05, ...}}

Any model can be scored by writing its answers in that shape (see FileRouter).
"""
import json
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline


class BaselineRouter:
    """Bag-of-words classifier with isotonic calibration, trained on older tickets.

    It is a floor to beat, not a proposal: it shows what calibrated confidence
    buys even from a cheap model, and gives the harness something to run today.
    """
    name = "baseline (TF-IDF + logistic regression, isotonic calibration)"

    def __init__(self):
        base = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=40000),
            LogisticRegression(C=8.0, max_iter=3000))
        self.model = CalibratedClassifierCV(base, method="isotonic", cv=5)

    def fit(self, tickets):
        self.model.fit([t["text"] for t in tickets], [t["team"] for t in tickets])
        return self

    def validation_answers(self, train, val):
        """Answers on the validation slice from a copy trained only on the earlier tickets."""
        return BaselineRouter().fit(train).answer(val)

    def answer(self, tickets):
        probs = self.model.predict_proba([t["text"] for t in tickets])
        classes = list(self.model.classes_)
        out = {}
        for t, p in zip(tickets, probs):
            p = p / p.sum()
            i = int(np.argmax(p))
            out[t["id"]] = {"type": "choice", "choice": classes[i],
                            "confidence": float(p[i]),
                            "probabilities": {c: float(x) for c, x in zip(classes, p)}}
        return out


class FileRouter:
    """Scores answers produced elsewhere (Jev, a frontier model, a rules engine).

    File format: one JSON object per line, {"id": <ticket id>, "answer": {<Choice answer>}}.
    An answer without "confidence" is thresholded on its top probability, and a
    {"type": "refusal"} answer is always sent to a person.
    """
    def __init__(self, path, val_path=None):
        self.path, self.val_path, self.name = path, val_path, f"answers from {path}"

    def fit(self, tickets):
        return self

    def answer(self, tickets):
        return self._load(self.path, tickets)

    def validation_answers(self, train, val):
        if not self.val_path:
            raise SystemExit("Pass --val-answers (answers for data/val_set.jsonl) so the threshold is not picked on the test set.")
        return self._load(self.val_path, val)

    def _load(self, path, tickets):
        out = {}
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                out[row["id"]] = row["answer"]
        missing = [t["id"] for t in tickets if t["id"] not in out]
        if missing:
            raise SystemExit(f"{len(missing)} tickets in {path} have no answer, e.g. {missing[:5]}")
        return out
