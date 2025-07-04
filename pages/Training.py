"""
Collect last-N feedback rows → JSONL ready for fine-tuning or few-shot injection.
"""
import streamlit as st, json
from pathlib import Path
from datetime import datetime
from src.utils import load_feedback

st.set_page_config(page_title="Training / Feedback", page_icon="🏋️‍♂️", layout="wide")
st.title("🏋️‍♂️ Training & Feedback")

N = st.number_input("How many latest corrections per doc-type?", 10, 200, 50)
feedback = load_feedback()

if not feedback:
    st.info("No feedback yet – run inference & save corrections first.")
    st.stop()

# -------- aggregate & trim --------
by_type: dict[str, list] = {}
for row in sorted(feedback, key=lambda r: r["timestamp"], reverse=True):
    by_type.setdefault(row["doc_type"], []).append(row)
    by_type[row["doc_type"]] = by_type[row["doc_type"]][:N]

export = []
for rows in by_type.values():
    for r in rows:
        export.append(
            {
                "messages": [
                    {"role": "system", "content": f"Document type: {r['doc_type']}"},
                    {"role": "assistant", "content": r["metadata_extracted"]},
                    {"role": "user", "content": r["metadata_corrected"]},
                ]
            }
        )

# -------- UI --------
st.markdown(f"Generating JSONL with **{len(export)}** examples.")
jsonl_path = Path("data") / f"ft_{datetime.utcnow():%Y%m%d_%H%M%S}.jsonl"

if st.button("Create JSONL"):
    jsonl_path.parent.mkdir(exist_ok=True)
    with open(jsonl_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(json.dumps(x, ensure_ascii=False) for x in export))
    st.success(f"Saved → `{jsonl_path}`")
    st.download_button("Download", jsonl_path.read_bytes(), file_name=jsonl_path.name)
