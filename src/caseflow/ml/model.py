from __future__ import annotations

import numpy as np
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

RANDOM_STATE = 42
N_FEATURES = 4

_X, _y = make_classification(
    n_samples=200,
    n_features=N_FEATURES,
    n_informative=3,
    n_redundant=1,
    n_clusters_per_class=1,
    random_state=RANDOM_STATE,
)

_model = LogisticRegression(random_state=RANDOM_STATE, max_iter=500)
_model.fit(_X, _y)


def predict(features: list[float]) -> float:
    if len(features) != N_FEATURES:
        raise ValueError(f"Expected {N_FEATURES} features, got {len(features)}")

    vector = np.asarray(features, dtype=float).reshape(1, -1)
    prediction = _model.predict_proba(vector)[0, 1]
    return float(prediction)
