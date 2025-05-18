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
    Returns a dict with keys: 'metadata', 'snippets', 'confidence'.
    """
    # Prepare a JSON template of the fields
    template = {field["name"]: None for field in schema}
    schema_json = json.dumps(template)

    # Encode image as a data URI
    buf = io.BytesIO()
    images[0].save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    # System prompt
    system_prompt = (
        "Extract the following fields from the document image. "
        "Respond in JSON with keys 'metadata', 'snippets', and 'confidence'."
    )
    # User content: image_url + text prompt
    user_content = [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {"type": "text",      "text": f"Fields schema: {schema_json}"}
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content}
    ]

    resp = get_chat_completion(
        messages,
        model=os.getenv("EXTRACT_MODEL", "gpt-4o-mini")
    )

    # Attempt to parse raw response; strip out any markdown fences or extra text
    try:
        return json.loads(resp)
    except json.JSONDecodeError:
        # Find the first JSON object in the response
        m = re.search(r"\{.*\}", resp, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                logging.error("Failed to parse inner JSON after regex")
        logging.error("Extraction JSON parse error; returning empty structure")
        return {"metadata": {}, "snippets": {}, "confidence": {}}
