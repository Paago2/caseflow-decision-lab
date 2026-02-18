"""Experiment 001: quick sanity check for active linear model scoring.

This script intentionally stays outside production runtime code.
It loads the active model from registry settings and prints a sample score.
"""

from __future__ import annotations

from caseflow.ml.registry import get_active_model


def main() -> None:
    sample_features = [0.1, -1.2, 2.3]
    model = get_active_model()
    score = model.predict(sample_features)

    print(f"experiment=exp_001 model_id={model.model_id} score={score:.6f}")


if __name__ == "__main__":
    main()
