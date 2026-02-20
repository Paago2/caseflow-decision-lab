from __future__ import annotations

import os

from golden_runner import run_golden


def test_golden_underwrite_regression() -> None:
    update = os.getenv("GOLDEN_UPDATE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    messages = run_golden(update=update)
    assert messages
