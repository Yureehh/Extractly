from __future__ import annotations

from PIL import Image

from extractly.pipeline.classification import classify_document


def classify(
    images: list[Image.Image],
    candidates: list[str],
    *,
    use_confidence: bool = False,
    n_votes: int = 5,
    system_prompt: str = "",
) -> dict:
    return classify_document(
        images,
        candidates,
        use_confidence=use_confidence,
        n_votes=n_votes,
        system_prompt=system_prompt or None,
    )
