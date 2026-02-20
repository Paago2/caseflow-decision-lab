from __future__ import annotations

from typing import Any

DOCUMENT_TYPE_PAYSTUB = "paystub"
DOCUMENT_TYPE_CREDIT_SUMMARY = "credit_summary"
DOCUMENT_TYPE_PROPERTY_VALUATION = "property_valuation"
DOCUMENT_TYPE_LOAN_APPLICATION = "loan_application"

_SUPPORTED_DOCUMENT_TYPES = {
    DOCUMENT_TYPE_PAYSTUB,
    DOCUMENT_TYPE_CREDIT_SUMMARY,
    DOCUMENT_TYPE_PROPERTY_VALUATION,
    DOCUMENT_TYPE_LOAN_APPLICATION,
}
_ALLOWED_OCCUPANCY = {"primary", "secondary", "investment"}


def _to_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Field '{field_name}' must be numeric/castable to float"
        ) from exc


def normalize_document(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise ValueError("Each document must be a JSON object")

    raw_type = doc.get("document_type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ValueError("'document_type' is required and must be a non-empty string")
    document_type = raw_type.strip().lower()
    if document_type not in _SUPPORTED_DOCUMENT_TYPES:
        supported = ", ".join(sorted(_SUPPORTED_DOCUMENT_TYPES))
        raise ValueError(
            f"Unsupported document_type '{document_type}'. Supported: {supported}"
        )

    cleaned: dict[str, Any] = {"document_type": document_type}

    if document_type == DOCUMENT_TYPE_PAYSTUB:
        if "gross_monthly_income" in doc:
            cleaned["gross_monthly_income"] = _to_float(
                doc.get("gross_monthly_income"), "gross_monthly_income"
            )

    if document_type == DOCUMENT_TYPE_CREDIT_SUMMARY:
        if "credit_score" in doc:
            cleaned["credit_score"] = _to_float(doc.get("credit_score"), "credit_score")
        if "total_monthly_debt" in doc:
            cleaned["total_monthly_debt"] = _to_float(
                doc.get("total_monthly_debt"), "total_monthly_debt"
            )

    if document_type == DOCUMENT_TYPE_PROPERTY_VALUATION:
        if "property_value" in doc:
            cleaned["property_value"] = _to_float(
                doc.get("property_value"), "property_value"
            )

    if document_type == DOCUMENT_TYPE_LOAN_APPLICATION:
        if "loan_amount" in doc:
            cleaned["loan_amount"] = _to_float(doc.get("loan_amount"), "loan_amount")
        if "occupancy" in doc:
            occupancy_raw = doc.get("occupancy")
            if not isinstance(occupancy_raw, str) or not occupancy_raw.strip():
                raise ValueError("Field 'occupancy' must be a non-empty string")
            occupancy = occupancy_raw.strip().lower()
            if occupancy not in _ALLOWED_OCCUPANCY:
                allowed = ", ".join(sorted(_ALLOWED_OCCUPANCY))
                raise ValueError(f"Field 'occupancy' must be one of: {allowed}")
            cleaned["occupancy"] = occupancy

    return cleaned


def extract_features_from_documents(
    documents: list[dict[str, Any]],
) -> tuple[dict[str, float | str], dict[str, int]]:
    if not isinstance(documents, list):
        raise ValueError("'documents' must be a list")

    features: dict[str, float | str] = {}
    source_summary: dict[str, int] = {}

    for raw_doc in documents:
        normalized = normalize_document(raw_doc)
        document_type = normalized["document_type"]
        source_summary[document_type] = source_summary.get(document_type, 0) + 1

        if document_type == DOCUMENT_TYPE_PAYSTUB:
            if "gross_monthly_income" in normalized:
                features["gross_monthly_income"] = normalized["gross_monthly_income"]

        if document_type == DOCUMENT_TYPE_CREDIT_SUMMARY:
            if "credit_score" in normalized:
                features["credit_score"] = normalized["credit_score"]
            if "total_monthly_debt" in normalized:
                features["total_monthly_debt"] = normalized["total_monthly_debt"]

        if document_type == DOCUMENT_TYPE_PROPERTY_VALUATION:
            if "property_value" in normalized:
                features["property_value"] = normalized["property_value"]

        if document_type == DOCUMENT_TYPE_LOAN_APPLICATION:
            if "loan_amount" in normalized:
                features["loan_amount"] = normalized["loan_amount"]
            if "occupancy" in normalized:
                features["occupancy"] = normalized["occupancy"]

    return features, source_summary


def required_downstream_fields() -> list[str]:
    return [
        "gross_monthly_income",
        "total_monthly_debt",
        "credit_score",
        "property_value",
        "loan_amount",
        "occupancy",
    ]


def missing_required(features: dict[str, Any]) -> list[str]:
    return [field for field in required_downstream_fields() if field not in features]
