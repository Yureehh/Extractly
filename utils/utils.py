"""
Utilities shared among Streamlit pages.
"""

from __future__ import annotations
import json
from pathlib import Path

# Get the project root directory (parent of the src directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
FEED_PATH = DATA_DIR / "feedback.jsonl"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
SCHEMAS_DIR.mkdir(exist_ok=True)


# ---------- 💾  feedback persistence ----------
def load_feedback() -> list[dict]:
    if not FEED_PATH.exists():
        return []
    with FEED_PATH.open(encoding="utf-8") as fp:
        return [json.loads(ln) for ln in fp if ln.strip()]


# ---------- 🔁  feedback upsert ----------
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
