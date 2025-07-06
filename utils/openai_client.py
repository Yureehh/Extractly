import os
from openai import OpenAI
from utils.utils import DEFAULT_OPENAI_MODEL

import logging

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OPENAI_API_KEY not found in env")
client = OpenAI(api_key=api_key)

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("extractor.log"), logging.StreamHandler()],
)


def get_chat_completion(messages, model=DEFAULT_OPENAI_MODEL, temperature=1):
    """
    Wrapper around OpenAI ChatCompletion.
    messages should be a list of dicts: {"role":..., "content":...}
    """
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature
        )
        return resp.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        raise
