"""
src/ocr_engine.py
A super-thin wrapper so you can swap engines without touching the rest of the app.
"""

from __future__ import annotations
from PIL import Image
import io
import base64
import os
import logging
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

    system_prompt = """
    You are an expert OCR (Optical Character Recognition) assistant. Your task is to extract ALL visible text from the document image with perfect accuracy.

    Instructions:
    1. Read every piece of text visible in the image, including:
    - Headers, titles, and headings
    - Body text and paragraphs
    - Table contents and data
    - Form fields and labels
    - Numbers, dates, and codes
    - Fine print and footnotes
    - Watermarks or stamps (if readable)

    2. Maintain the logical reading order (top to bottom, left to right)
    3. Preserve line breaks and spacing where meaningful
    4. Return ONLY the literal text - no commentary, no JSON formatting
    5. If text is unclear or partially obscured, make your best attempt
    6. Format as plain text but keep line breaks as they appear so humans can read it easily
    """

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


def run_ocr(pages: list[Image.Image]) -> str:
    """
    Concatenate OCR text from **all** pages with double newlines.
    Now LLM-only.
    """
    return "\n\n".join(_ocr_llm(p) for p in pages)
