from __future__ import annotations

from pathlib import Path

import yaml

LOW_CREDIT_SCORE = "LOW_CREDIT_SCORE"
HIGH_LTV = "HIGH_LTV"
HIGH_DTI = "HIGH_DTI"

_POLICY_PATH = Path("configs") / "policy.yaml"
_cached_policy: dict | None = None


def load_policy() -> dict:
    global _cached_policy
    if _cached_policy is not None:
        return _cached_policy

    if not _POLICY_PATH.is_file():
        raise ValueError(f"Policy config not found: {_POLICY_PATH}")

    payload = yaml.safe_load(_POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Policy config root must be a mapping")

    policy_version = payload.get("policy_version")
    thresholds = payload.get("thresholds")
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise ValueError("policy_version must be a non-empty string")
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be an object")

    for section_name in ("approve", "review"):
        section = thresholds.get(section_name)
        if not isinstance(section, dict):
            raise ValueError(f"thresholds.{section_name} must be an object")

        for key in ("min_credit_score", "max_ltv", "max_dti"):
            if key not in section:
                raise ValueError(f"thresholds.{section_name}.{key} is required")
            try:
                section[key] = float(section[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"thresholds.{section_name}.{key} must be numeric"
                ) from exc

    _cached_policy = payload
    return _cached_policy


def clear_policy_cache() -> None:
    global _cached_policy
    _cached_policy = None


def evaluate_policy(features: dict) -> tuple[str, list[str]]:
    policy = load_policy()
    thresholds = policy["thresholds"]
    approve = thresholds["approve"]
    review = thresholds["review"]

    missing_keys = [
        key for key in ("credit_score", "ltv", "dti") if key not in features
    ]
    if missing_keys:
        raise ValueError("Missing policy feature keys: " + ", ".join(missing_keys))

    try:
        credit_score = float(features["credit_score"])
        ltv = float(features["ltv"])
        dti = float(features["dti"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Policy features must be numeric") from exc

    if (
        credit_score >= approve["min_credit_score"]
        and ltv <= approve["max_ltv"]
        and dti <= approve["max_dti"]
    ):
        return "approve", []

    reasons: list[str] = []
    if credit_score < approve["min_credit_score"]:
        reasons.append(LOW_CREDIT_SCORE)
    if ltv > approve["max_ltv"]:
        reasons.append(HIGH_LTV)
    if dti > approve["max_dti"]:
        reasons.append(HIGH_DTI)

    if (
        credit_score >= review["min_credit_score"]
        and ltv <= review["max_ltv"]
        and dti <= review["max_dti"]
    ):
        return "review", reasons

    decline_reasons: list[str] = []
    if credit_score < review["min_credit_score"]:
        decline_reasons.append(LOW_CREDIT_SCORE)
    if ltv > review["max_ltv"]:
        decline_reasons.append(HIGH_LTV)
    if dti > review["max_dti"]:
        decline_reasons.append(HIGH_DTI)

    if not decline_reasons:
        decline_reasons = reasons

    return "decline", decline_reasons
