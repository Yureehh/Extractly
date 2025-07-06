"""
Thin wrapper so backend code can reuse Streamlit-agnostic persistence.
"""

import json
from datetime import timezone
from pathlib import Path
from datetime import datetime

# Get the project root directory (parent of the src directory)
PROJECT_ROOT = Path(__file__).parent.parent
FEED_PATH = PROJECT_ROOT / "data" / "feedback.jsonl"
FEED_PATH.parent.mkdir(exist_ok=True)


def record_feedback(doc_id: str, doc_type: str, extracted: dict, corrected: dict):
    row = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "metadata_extracted": extracted,
        "metadata_corrected": corrected,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with FEED_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")
