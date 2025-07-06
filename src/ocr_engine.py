"""
src/ocr_engine.py
A super-thin wrapper so you can swap engines without touching the rest of the app.
"""

from __future__ import annotations
from typing import List
from PIL import Image
import io
import base64
import os
import logging
import pytesseract
from openai import OpenAI
from utils.utils import DEFAULT_OPENAI_MODEL

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY not found in env")

# ── local OpenAI helper ────────────────────────────────────────────
_client = OpenAI(api_key=api_key)  # ①
_VISION_MODEL = os.getenv("OCR_MODEL", DEFAULT_OPENAI_MODEL)  # ②


def _ocr_llm(page: Image.Image) -> str:
    """Do a *vision* chat-completion round-trip and return plain text."""
    buf = io.BytesIO()
    page.save(buf, format="PNG")
    data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    system_prompt = (
        "You are an OCR engine. Return ONLY the literal Unicode text that "
        "appears in the image, in reading order. No commentary, no JSON, "
        "no formatting besides line-breaks."
    )

    msg = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]

    try:
        resp = _client.chat.completions.create(model=_VISION_MODEL, messages=msg)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"LLM-OCR failed: {e}")
        return ""


# ── classic engines ───────────────────────────────────────────────
_TESS_CFG = "--psm 6"


def _ocr_tesseract(page: Image.Image) -> str:
    return pytesseract.image_to_string(page, config=_TESS_CFG)


# ── dispatch helper ───────────────────────────────────────────────
_ENGINE_MAP = {
    "tesseract": _ocr_tesseract,
    "llm-ocr": _ocr_llm,  # ③
}


def run_ocr(pages: List[Image.Image], engine: str = "tesseract") -> str:
    """
    Concatenate OCR text from **all** pages with double newlines.
    `engine` may be 'tesseract' or 'llm-ocr' (case-insensitive).
    """
    fn = _ENGINE_MAP.get(engine.lower(), _ocr_tesseract)
    return "\n\n".join(fn(p) for p in pages)
