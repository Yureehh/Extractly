# utils/classifier.py

import os
import io
import base64
import json
import logging
from PIL import Image
from .openai_client import get_chat_completion


def classify(images: list[Image.Image], candidates: list) -> dict:
    """
    Classify document type by sending the first page image to the LLM.
    Returns a dict with keys 'doc_type' and optional 'reasoning'.
    """
    # Encode image as a data URI
    buf = io.BytesIO()
    images[0].save(buf, format="PNG")
    data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    # System prompt listing the choices
    system_prompt = f"Choose exactly one document type from: {candidates}. Return only exactly the type name, no other text or explanation."
    # User content: text + image_url segment
    user_content = [
        {"type": "text", "text": system_prompt},
        {"type": "image_url", "image_url": {"url": data_uri}},
    ]

    messages = [
        {"role": "system", "content": "You are a document classification assistant."},
        {"role": "user", "content": user_content},
    ]

    resp = get_chat_completion(
        messages, model=os.getenv("CLASSIFY_MODEL", "gpt-4o-mini")
    )

    try:
        print(f"LLM response: {resp}")
        return json.loads(resp)
    except Exception:
        logging.warning("Failed to parse classification JSON; returning raw response")
        return {"doc_type": resp.strip(), "reasoning": resp.strip()}
