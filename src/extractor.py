from __future__ import annotations

from PIL import Image

from extractly.domain.models import SchemaField
from extractly.pipeline.extraction import extract_metadata


def extract(
    images: list[Image.Image],
    schema: list[dict],
    ocr_text: str | None = None,
    *,
    with_confidence: bool = False,
    system_prompt: str = "",
) -> dict:
    fields = [
        SchemaField(
            name=field.get("name", ""),
            field_type=field.get("type", "string"),
            required=field.get("required", False),
            description=field.get("description", ""),
            example=field.get("example", ""),
            enum_values=list(field.get("enum", []) or []),
        )
        for field in schema
    ]

    return extract_metadata(
        images,
        fields,
        ocr_text=ocr_text,
        with_confidence=with_confidence,
        system_prompt=system_prompt or None,
    )
