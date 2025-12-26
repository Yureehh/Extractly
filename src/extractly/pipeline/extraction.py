from __future__ import annotations

import base64
import contextlib
import io
import json
import re
from typing import Any

from PIL import Image

from extractly.config import load_config
from extractly.domain.models import SchemaField
from extractly.integrations.openai_client import get_chat_completion
from extractly.logging import get_logger


logger = get_logger(__name__)


DEFAULT_EXTRACTION_PROMPT = """
You are a metadata extraction specialist. Extract the requested fields with high accuracy.
Return JSON with keys: metadata, snippets, confidence. Use null when a field is missing.
"""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _truncate(text: str, max_chars: int = 64_000) -> str:
    return text[:max_chars]


def _schema_payload(fields: list[SchemaField]) -> dict[str, Any]:
    return {
        field.name: {
            "type": field.field_type,
            "required": field.required,
            "description": field.description,
            "example": field.example,
            "enum": field.enum_values,
        }
        for field in fields
    }


def extract_metadata(
    images: list[Image.Image],
    fields: list[SchemaField],
    *,
    ocr_text: str | None = None,
    with_confidence: bool = False,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = load_config()
    field_names = [field.name for field in fields]

    schema_json = json.dumps(_schema_payload(fields), ensure_ascii=False)

    user_content = [
        {"type": "image_url", "image_url": {"url": _image_to_data_uri(images[0])}},
        {"type": "text", "text": f"Schema: {schema_json}"},
    ]
    if ocr_text:
        user_content.append(
            {
                "type": "text",
                "text": "OCR context:\n" + _truncate(ocr_text),
            }
        )

    messages = [
        {"role": "system", "content": system_prompt or DEFAULT_EXTRACTION_PROMPT},
        {"role": "user", "content": user_content},
    ]

    response = get_chat_completion(messages, model=config.extract_model)
    if not response.strip():
        raise RuntimeError("Empty extraction response")

    raw: dict[str, Any] | None = None
    with contextlib.suppress(json.JSONDecodeError):
        raw = json.loads(response)

    if raw is None and (match := re.search(r"\{.*\}", response, flags=re.S)):
        with contextlib.suppress(json.JSONDecodeError):
            raw = json.loads(match.group())

    if not isinstance(raw, dict):
        logger.error("Bad extraction JSON. Returning blanks.")
        raw = {}

    raw_meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    raw_snippets = (
        raw.get("snippets") if isinstance(raw.get("snippets"), dict) else {}
    )
    raw_conf = (
        raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {}
    )


    if with_confidence and not raw_conf:
        raw_conf = {name: 1.0 if raw_meta.get(name) else 0.0 for name in field_names}

    metadata = {name: raw_meta.get(name) for name in field_names}
    snippets = {name: raw_snippets.get(name) for name in field_names}

    confidence = {}
    if with_confidence:
        confidence = {name: raw_conf.get(name, 0.0) for name in field_names}

    return {
        "metadata": metadata,
        "snippets": snippets,
        "confidence": confidence,
    }
