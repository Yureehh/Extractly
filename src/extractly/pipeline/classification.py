from __future__ import annotations

import base64
import io
from statistics import StatisticsError, mode
from typing import Any

from PIL import Image

from extractly.config import load_config
from extractly.integrations.openai_client import get_chat_completion
from extractly.logging import get_logger


logger = get_logger(__name__)


DEFAULT_CLASSIFIER_PROMPT = """
You are an expert document classifier. Choose the most likely document type based on layout,
visual cues, and key text. Respond only with a single label from the provided list.
If uncertain, choose "Unknown".
"""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def classify_document(
    images: list[Image.Image],
    candidates: list[str],
    *,
    use_confidence: bool = False,
    n_votes: int = 3,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = load_config()
    prompt = system_prompt or DEFAULT_CLASSIFIER_PROMPT

    def _single_vote() -> str:
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Choose one type from: {candidates}.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_to_data_uri(images[0])},
                    },
                ],
            },
        ]
        return get_chat_completion(messages, model=config.classify_model).strip()

    if not use_confidence:
        return {"doc_type": _single_vote()}

    votes = [_single_vote() for _ in range(n_votes)]
    try:
        best = mode(votes)
        confidence = votes.count(best) / n_votes
    except StatisticsError:
        best, confidence = votes[0], 1 / n_votes

    return {"doc_type": best, "confidence": confidence}
