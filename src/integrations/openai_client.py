from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from src.config import load_config
from src.logging import get_logger


logger = get_logger(__name__)


def _is_reasoning_model(model: str) -> bool:
    name = model.lower().strip()
    return name.startswith(("o1", "o3", "o4", "gpt-5"))


def get_chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.0,
) -> str:
    config = load_config()
    if not config.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=config.openai_api_key)
    attempts = config.max_retries + 1
    if not _is_reasoning_model(model):
        temperature = 0.0

    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=config.request_timeout_s,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(
                "OpenAI request failed (attempt %s/%s): %s",
                attempt + 1,
                attempts,
                exc,
            )
            if attempt >= config.max_retries:
                raise
            time.sleep(config.retry_backoff_s * (attempt + 1))

    return ""
