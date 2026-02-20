from __future__ import annotations

import io

from caseflow.core.settings import get_settings

_SUPPORTED_CONTENT_TYPES = {
    "text/plain",
    "application/pdf",
    "image/png",
    "image/jpeg",
}


def _read_text_plain(document_bytes: bytes) -> tuple[str, dict[str, object]]:
    try:
        text = document_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "text/plain content must be valid UTF-8 (strict decode failed)"
        ) from exc

    return text, {
        "method": "plain_text",
        "engine": "builtin",
        "char_count": len(text),
    }


def extract_text(
    document_bytes: bytes, content_type: str
) -> tuple[str, dict[str, object]]:
    normalized_content_type = content_type.strip().lower()
    if normalized_content_type not in _SUPPORTED_CONTENT_TYPES:
        supported = ", ".join(sorted(_SUPPORTED_CONTENT_TYPES))
        raise ValueError(
            f"Unsupported content_type '{content_type}'. Supported: {supported}"
        )

    settings = get_settings()
    ocr_engine = settings.ocr_engine

    if normalized_content_type == "text/plain":
        return _read_text_plain(document_bytes)

    if normalized_content_type == "application/pdf":
        if ocr_engine == "noop":
            raise ValueError(
                "application/pdf extraction not supported yet with OCR_ENGINE=noop"
            )
        raise ValueError(
            "application/pdf extraction for OCR_ENGINE=tesseract is not implemented "
            "yet"
        )

    if ocr_engine == "noop":
        raise ValueError(
            f"{normalized_content_type} extraction requires OCR_ENGINE=tesseract "
            "(noop does not process images)"
        )

    try:
        import pytesseract  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError(
            "OCR_ENGINE=tesseract requested but pytesseract is not installed. "
            "Install with: pip install pytesseract"
        ) from exc

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "OCR_ENGINE=tesseract requested but Pillow is not installed. "
            "Install with: pip install pillow"
        ) from exc

    try:
        image = Image.open(io.BytesIO(document_bytes))
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        raise ValueError(f"Image OCR failed: {exc}") from exc

    return text, {
        "method": "ocr",
        "engine": "tesseract",
        "char_count": len(text),
    }
