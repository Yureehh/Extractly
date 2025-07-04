"""
Batch inference page – thumbnails, extraction, and inline correction grid.
"""
import streamlit as st
from uuid import uuid4
import time, json
from src.preprocess import preprocess
from src.schema_manager import SchemaManager
from src.classifier import classify
from src.extractor import extract
from src.utils import show_thumbnails, save_feedback, load_feedback, generate_doc_id

st.set_page_config(page_title="Inference", page_icon="🔍", layout="wide")
st.title("🔍 Inference")

schema_mgr = SchemaManager()
files = st.file_uploader("Upload PDFs or images",
                         type=["pdf", "png", "jpg", "jpeg"],
                         accept_multiple_files=True)

if not files:
    st.info("Awaiting uploads …")
    st.stop()

thumbs = show_thumbnails(files)  # ❄ just eye-candy

if st.button("Run extraction on all docs"):
    rows = []
    progress = st.progress(0.0, text="Extracting …")
    for idx, file in enumerate(files, start=1):
        images = preprocess(file)
        # -------- classification
        cls = classify(images, schema_mgr.get_types())
        doc_type = cls["doc_type"]
        # -------- fields schema
        fields = schema_mgr.get(doc_type) or []
        # -------- extraction
        meta = extract(images, fields)
        rows.append(
            {
                "doc_id"            : generate_doc_id(file),
                "file_name"         : file.name,
                "doc_type"          : doc_type,
                "metadata_extracted": json.dumps(meta["metadata"], ensure_ascii=False),
                "metadata_corrected": json.dumps(meta["metadata"], ensure_ascii=False),  # editable
                "timestamp"         : time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        progress.progress(idx / len(files))

    st.success("Extraction done. Edit any wrong cell and press **Save** ↓")
    edited = st.data_editor(rows, key="editor", num_rows="dynamic")

    if st.button("Save"):
        for row in edited:
            save_feedback(row)   # JSON-based persistence
        st.success("👍 Corrections saved.")
