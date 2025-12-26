from __future__ import annotations

import base64
import io
from typing import Iterable
from PIL import Image

from extractly.config import load_config
from extractly.integrations.openai_client import get_chat_completion
from extractly.logging import get_logger


logger = get_logger(__name__)


_OCR_SYSTEM_PROMPT = """
You are an expert OCR (Optical Character Recognition) assistant. Extract every visible piece
of text from the document image. Preserve the reading order and line breaks where meaningful.
Return only the raw text content.
"""


def _page_to_data_uri(page: Image.Image) -> str:
    buf = io.BytesIO()
    page.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def ocr_page(page: Image.Image) -> str:
    config = load_config()
    messages = [
        {"role": "system", "content": _OCR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _page_to_data_uri(page)}},
            ],
        },
    ]

    return get_chat_completion(messages, model=config.ocr_model, temperature=0.0)


def run_ocr(pages: Iterable[Image.Image]) -> str:
    outputs: list[str] = []
    for page in pages:
        try:
            outputs.append(ocr_page(page))
        except Exception as exc:
            logger.error("OCR failed: %s", exc)
            outputs.append("")
    return "\n\n".join(outputs).strip()
