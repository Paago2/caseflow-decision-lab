from __future__ import annotations

import hashlib
import math
import re

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def embed_text(text: str, dims: int = 128) -> list[float]:
    if dims <= 0:
        raise ValueError("dims must be > 0")

    vector = [0.0] * dims
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], byteorder="big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    return _normalize(vector)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding vectors must have equal length")
    return sum(lv * rv for lv, rv in zip(left, right))
