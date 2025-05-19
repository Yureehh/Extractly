import os
import io
import base64
import json
import logging
import re
from PIL import Image
from .openai_client import get_chat_completion

def extract(images: list[Image.Image], schema: list[dict]) -> dict:
    """
    Extract metadata from the document image using the provided schema.
    Returns a dict with keys: 'metadata', 'snippets', 'confidence',
    and ensures only the requested fields appear.
    """
    # 1) Build field list
    field_names = [field["name"] for field in schema]
    template = {name: None for name in field_names}
    schema_json = json.dumps(template)

    # 2) Encode first image as a data URI
    buf = io.BytesIO()
    images[0].save(buf, format="PNG")
    data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    # 3) Stronger system prompt: enforce exact keys
    system_prompt = (
        "You are a metadata extraction assistant. "
        "Extract exactly the requested fields from the document image.  "
        "Do NOT include any other fields.  "
        "Respond **only** with a JSON object with three top-level keys: "
        "`metadata`, `snippets`, and `confidence`.  "
        "`metadata` must contain exactly these fields: "
        f"{field_names}.  If a field is not found, set its value to null.  "
        "`snippets` must map each field name to a short example text excerpt.  "
        "`confidence` must map each field name to a confidence score between 0 and 1."
    )

    user_content = [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {"type": "text",      "text": f"Fields schema: {schema_json}"}
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content}
    ]

    # 4) Call the LLM
    resp = get_chat_completion(
        messages,
        model=os.getenv("EXTRACT_MODEL", "gpt-4o-mini")
    )

    # 5) Parse and filter the JSON
    raw = None
    try:
        raw = json.loads(resp)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", resp, flags=re.DOTALL)
        if m:
            try:
                raw = json.loads(m.group())
            except json.JSONDecodeError:
                logging.error("Failed to parse inner JSON")
    if not isinstance(raw, dict):
        logging.error("Extraction JSON parse error; returning empty structure")
        return {
            "metadata": {n: None for n in field_names},
            "snippets": {n: None for n in field_names},
            "confidence": {n: None for n in field_names},
        }

    # 6) Enforce only requested fields
    raw_meta = raw.get("metadata", {})
    raw_snips = raw.get("snippets", {})
    raw_conf = raw.get("confidence", {})

    metadata = {n: raw_meta.get(n) for n in field_names}
    snippets = {n: raw_snips.get(n) for n in field_names}
    confidence = {n: raw_conf.get(n) for n in field_names}

    return {
        "metadata": metadata,
        "snippets": snippets,
        "confidence": confidence,
    }
