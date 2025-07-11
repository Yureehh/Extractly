"""
Utilities shared among Streamlit pages.
"""

from __future__ import annotations
import io
import json
import hashlib
from pathlib import Path
from typing import Iterable
import streamlit as st
from PIL import Image

# Get the project root directory (parent of the src directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
FEED_PATH = DATA_DIR / "feedback.jsonl"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
SCHEMAS_DIR.mkdir(exist_ok=True)

DEFAULT_OPENAI_MODEL = "o4-mini"  # Default model for OpenAI API calls


# ---------- 🖼️  thumbnails ----------
def show_thumbnails(files: Iterable) -> list[Image.Image]:
    cols = st.columns(5)
    thumbs = []
    for idx, file in enumerate(files):
        img = Image.open(io.BytesIO(file.getvalue()))
        thumb = img.resize((180, 240), Image.Resampling.LANCZOS)
        with cols[idx % 5]:
            st.image(thumb, caption=file.name)
        thumbs.append(thumb)
    return thumbs


# ---------- 💾  feedback persistence ----------
def save_feedback(row: dict) -> None:
    """Append one corrected row (dict) into feedback.jsonl."""
    with FEED_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_feedback() -> list[dict]:
    if not FEED_PATH.exists():
        return []
    with FEED_PATH.open(encoding="utf-8") as fp:
        return [json.loads(ln) for ln in fp if ln.strip()]


# ---------- 🔑  deterministic id ----------
def generate_doc_id(uploaded_file) -> str:
    """Create stable ID from file checksum."""
    return hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:16]


def upsert_feedback(new_row: dict, path: Path = None):
    """Write row; overwrite existing line with same doc_id."""
    if path is None:
        path = FEED_PATH

    rows = []
    if path.exists():
        with path.open(encoding="utf-8") as fp:
            rows = [json.loads(x) for x in fp if x.strip()]

    rows = [r for r in rows if r.get("doc_id") != new_row["doc_id"]]
    rows.append(new_row)

    with path.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------- 🔍  diff fields ----------
def diff_fields(original: dict, corrected: dict) -> list[str]:
    """
    Return a list of field names whose value changed (case-sensitive compare).
    """
    return [k for k, v in corrected.items() if v != original.get(k)]
