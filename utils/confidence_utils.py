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


def temp_scale(raw_scores, T):
    """Temperature-scale a list/np.array of raw confidences."""
    import scipy.special as sp

    logits = np.log(np.clip(raw_scores, 1e-6, 1 - 1e-6))
    return sp.softmax(logits / T)


# ────────────────────────────────────────────────────────────────────
# Extraction-side confidence – *LLM-as-a-Judge only* (no heuristics)
# ────────────────────────────────────────────────────────────────────


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
        "You are a QA assistant. For each field, output a number in [0,1] that "
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
            return {k: float(max(0.0, min(1.0, float(v)))) for k, v in judged.items()}
    return {name: 0.5 for name in fields_to_judge}  # neutral fallback


def score_confidence(
    meta: Dict[str, str | None],
    schema: List[Dict],
) -> Dict[str, float]:
    """
    Ask the LLM to score every field directly.
    If the LLM reply cannot be parsed, fall back to 0.50 for that field.
    N.B: we could use majority_vote() here, but it’s more complex and costly to reach sufficient confidence.

    Returns
    -------
    Dict[str, float]
        A dense mapping field-name → confidence ∈ [0,1].
    """
    # Build a dict with **all** fields the caller expects
    to_judge: Dict[str, str | None] = {f["name"]: meta.get(f["name"]) for f in schema}

    # Find the PIL image already in the call-stack (extract() passes it)
    from inspect import currentframe, getouterframes

    image = None
    for frame in getouterframes(currentframe(), 2):
        images = frame.frame.f_locals.get("images")
        if images:
            image = images[0]
            break
    if image is None:  # extremely unlikely, but guard anyway
        return {k: 0.50 for k in to_judge}  # neutral confidence

    judged = llm_judge_scores(image, to_judge)  # ← single call to the judge
    # Ensure every key is present, default 0.50
    return {k: judged.get(k, 0.50) for k in to_judge}
