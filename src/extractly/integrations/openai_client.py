from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from extractly.config import load_config
from extractly.logging import get_logger


logger = get_logger(__name__)


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        config = load_config()
        _client = OpenAI(api_key=config.openai_api_key, timeout=config.request_timeout_s)
    return _client


def get_chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.2,
    max_retries: int | None = None,
    timeout_s: int | None = None,
) -> str:
    config = load_config()
    retries = max_retries if max_retries is not None else config.max_retries
    timeout = timeout_s if timeout_s is not None else config.request_timeout_s

    if not config.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your environment.")

    for attempt in range(retries + 1):
        try:
            response = get_client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("OpenAI request failed (attempt %s): %s", attempt + 1, exc)
            if attempt >= retries:
                raise
            time.sleep(config.retry_backoff_s * (attempt + 1))

    return ""
