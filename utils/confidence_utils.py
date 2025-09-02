# utils/confidence_utils.py

import os
import io
import base64
import contextlib
import json
from typing import Dict, List

import numpy as np
from PIL import Image

from utils.openai_client import get_chat_completion
from utils.utils import DEFAULT_OPENAI_MODEL


def majority_vote(probs, labels):
    """Return (winner, confidence) given an array [[p(type1)…], …]."""
    mean = probs.mean(axis=0)
    idx = np.argmax(mean)
    return labels[idx], float(mean[idx])


# ────────────────────────────────────────────────────────────────────
# LLM-as-a-Judge helper  (generic, can be re-used elsewhere)
# ────────────────────────────────────────────────────────────────────
def llm_judge_scores(
    image: Image.Image,
    fields_to_judge: Dict[str, str | None],
    *,
    model: str | None = None,
) -> Dict[str, float]:
    """
    Ask an LLM to rate each field value with a probability [0,1].

    Parameters
    ----------
    image : PIL.Image.Image
        First page (as in your extract pipeline).
    fields_to_judge : mapping name -> extracted value
    model : str | None
        Override the model used for judging, otherwise env/DEFAULT_OPENAI_MODEL.
    """
    if not fields_to_judge:
        return {}

    # encode the page as data-URI (tiny – first page thumb is enough)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    sys = (
        "You are a QA assistant. For each field, output a number in [0,100] that "
        "represents how likely the proposed value is correct *given the image*. "
        "Return ONLY a flat JSON mapping."
    )
    usr = [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {
            "type": "text",
            "text": f"Evaluate these: {json.dumps(fields_to_judge, ensure_ascii=False)}",
        },
    ]

    rsp = get_chat_completion(
        [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
        model=(model or os.getenv("VERIFY_MODEL", DEFAULT_OPENAI_MODEL)),
    )

    with contextlib.suppress(Exception):
        judged = json.loads(rsp)
        if isinstance(judged, dict):
            # coerce to float, clamp to [0,1]
            return {
                k: float(max(0.0, min(1.0, float(v) / 100.0)))
                for k, v in judged.items()
            }
    return {name: 0.5 for name in fields_to_judge}  # neutral fallback


def heuristic_confidence_score(metadata: dict, schema: list[dict]) -> dict:
    """
    Heuristic confidence scoring for extracted metadata (fallback method).
    Returns a dict with field names as keys and confidence scores (0-1) as values.
    """
    confidence_scores = {}

    for field in schema:
        field_name = field["name"]
        value = metadata.get(field_name)

        if value is None or value == "" or value == "null":
            confidence_scores[field_name] = 0.0
        elif isinstance(value, str):
            if len(value.strip()) == 0:
                confidence_scores[field_name] = 0.0
            elif len(value.strip()) < 3:
                confidence_scores[field_name] = 0.3
            elif len(value.strip()) < 10:
                confidence_scores[field_name] = 0.6
            else:
                # Check for patterns that suggest good extraction
                has_numbers = any(c.isdigit() for c in value)
                has_letters = any(c.isalpha() for c in value)
                has_structure = any(c in value for c in ["-", "/", ".", "@"])

                base_confidence = 0.7
                if has_numbers and has_letters:
                    base_confidence += 0.1
                if has_structure:
                    base_confidence += 0.1

                confidence_scores[field_name] = min(base_confidence, 1.0)
        else:
            confidence_scores[field_name] = 0.9

    return confidence_scores


def score_confidence(
    meta: Dict[str, str | None],
    schema: List[Dict],
    use_llm: bool = True,
) -> Dict[str, float]:
    """
    Score confidence for extracted metadata fields.

    Parameters
    ----------
    meta : Dict[str, str | None]
        Extracted metadata
    schema : List[Dict]
        Schema definition
    use_llm : bool
        Whether to use LLM-based scoring (default) or heuristic fallback

    Returns
    -------
    Dict[str, float]
        A dense mapping field-name → confidence ∈ [0,1].
    """
    # Build a dict with **all** fields the caller expects
    to_judge: Dict[str, str | None] = {f["name"]: meta.get(f["name"]) for f in schema}

    if not use_llm:
        return heuristic_confidence_score(meta, schema)

    # Find the PIL image already in the call-stack (extract() passes it)
    from inspect import currentframe, getouterframes

    image = None
    for frame in getouterframes(currentframe(), 2):
        if images := frame.frame.f_locals.get("images"):
            image = images[0]
            break

    if image is None:  # fallback to heuristic if no image found
        return heuristic_confidence_score(meta, schema)

    try:
        judged = llm_judge_scores(image, to_judge)  # ← single call to the judge
        heuristic_scores = heuristic_confidence_score(meta, schema)
        return {k: judged.get(k, heuristic_scores.get(k, 0.50)) for k in to_judge}
    except Exception:
        # Fallback to heuristic scoring if LLM fails
        return heuristic_confidence_score(meta, schema)
