import contextlib
import os
import io
import base64
import json
import logging
import re
from typing import List, Dict
from PIL import Image
from utils.openai_client import get_chat_completion
from utils.utils import DEFAULT_OPENAI_MODEL
from utils.confidence_utils import score_confidence


def _truncate(txt: str, max_chars: int = 64_000) -> str:
    """Guard-rail so we don't blow up the context window with huge OCR dumps."""
    return txt[:max_chars]


def extract(
    images: List[Image.Image],
    schema: List[Dict],
    ocr_text: str | None = None,  # Changed from Mapping to str
    *,  # keyword-only "tuning" flags
    with_confidence: bool = False,
    system_prompt: str = "",
) -> Dict:
    """
    Return a dict with exactly three top-level keys:
        metadata   – field -> value
        snippets   – field -> supporting text (ocr or model)
        confidence – field -> float in [0,1]  (empty if with_confidence=False)
    """
    # 1️⃣  template & helpers --------------------------------------------------
    field_names = [f["name"] for f in schema]
    blank_dict = {n: None for n in field_names}
    schema_json = json.dumps(blank_dict, ensure_ascii=False)

    buf = io.BytesIO()
    images[0].save(buf, format="PNG")
    data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    usr = [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {"type": "text", "text": f"Fields schema: {schema_json}"},
    ]

    if ocr_text:
        usr.append(
            {
                "type": "text",
                "text": "Extra context (OCR dump):\n\n" + _truncate(ocr_text),
            }
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": usr},
    ]

    # 2️⃣  LLM call ------------------------------------------------------------
    resp = get_chat_completion(
        messages, model=os.getenv("EXTRACT_MODEL", DEFAULT_OPENAI_MODEL)
    )

    if not resp.strip():
        raise RuntimeError("empty LLM response")

    # 3️⃣  JSON-safe parse -----------------------------------------------------
    raw: Dict | None = None
    with contextlib.suppress(json.JSONDecodeError):
        raw = json.loads(resp)

    if raw is None and (m := re.search(r"\{.*\}", resp, flags=re.S)):
        with contextlib.suppress(json.JSONDecodeError):
            raw = json.loads(m.group())

    if not isinstance(raw, dict):
        logging.error("Bad extraction JSON → returning blanks")
        raw = {}

    # 4️⃣  normalise sections --------------------------------------------------
    raw_meta = raw.get("metadata") or {}
    raw_snip = raw.get("snippets") or {}
    raw_conf = raw.get("confidence") or {}

    # force dicts (LLMs sometimes give a scalar there)
    if not isinstance(raw_meta, dict):
        raw_meta = {}
    if not isinstance(raw_snip, dict):
        raw_snip = {}
    if not isinstance(raw_conf, dict):
        raw_conf = {}

    # merge external OCR into snippets (OCR wins)
    if ocr_text:  # Changed from isinstance(ocr_text, dict) check
        raw_snip["ocr_content"] = ocr_text

    # 5️⃣  fallback confidence --------------------------------------------------
    if with_confidence and not raw_conf:
        # heuristic: 1.0 if field present & not null, else 0.0
        raw_conf = score_confidence(raw_meta, schema)

    # 6️⃣  final payload with *exact* keys -------------------------------------
    return {
        "metadata": {n: raw_meta.get(n) for n in field_names},
        "snippets": {n: raw_snip.get(n) for n in field_names},
        "confidence": {n: raw_conf.get(n) for n in field_names}
        if with_confidence
        else {},
    }
