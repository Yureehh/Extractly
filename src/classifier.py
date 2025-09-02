# utils/classifier.py

import os
import io
import base64
from PIL import Image
from utils.openai_client import get_chat_completion
from statistics import mode, StatisticsError
from utils.utils import DEFAULT_OPENAI_MODEL


def classify(
    images: list[Image.Image],
    candidates: list[str],
    *,
    use_confidence: bool = False,  # ⭐ NEW toggle
    n_votes: int = 5,  # number of self-consistency calls
    system_prompt: str | None = None,  # NEW: Allow custom system prompt
) -> dict:
    """Returns {'doc_type': str} or additionally a 'confidence' field."""

    def _single_vote() -> str:
        buf = io.BytesIO()
        images[0].save(buf, format="PNG")
        data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

        # NEW: Use custom system prompt if provided
        if system_prompt is None:
            sys_content = "You are a document classifier."
        else:
            sys_content = system_prompt

        prompt = f"Choose one type from: {candidates}. Return only the type."
        msgs = [
            {"role": "system", "content": sys_content},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ]
        return get_chat_completion(
            msgs, model=os.getenv("CLASSIFY_MODEL", DEFAULT_OPENAI_MODEL)
        ).strip()

    if not use_confidence:
        return {"doc_type": _single_vote()}

    votes = [_single_vote() for _ in range(n_votes)]
    try:
        best = mode(votes)
        confidence = votes.count(best) / n_votes
    except StatisticsError:  # all votes different
        best, confidence = votes[0], 1 / n_votes

    return {"doc_type": best, "confidence": confidence}
