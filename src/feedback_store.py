"""
Thin wrapper so backend code can reuse Streamlit-agnostic persistence.
"""
import json
from pathlib import Path
from datetime import datetime

FEED_PATH = Path("data") / "feedback.jsonl"
FEED_PATH.parent.mkdir(exist_ok=True)

def record_feedback(doc_id: str, doc_type: str,
                    extracted: dict, corrected: dict):
    row = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "metadata_extracted": extracted,
        "metadata_corrected": corrected,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
    }
    with FEED_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")
