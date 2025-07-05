"""
Batch Extraction – multi-doc classification, OCR, extraction & correction UI.
"""

from __future__ import annotations
import io
import json
from datetime import datetime, timezone
from typing import List

import streamlit as st
import pandas as pd

from src.preprocess import preprocess
from src.schema_manager import SchemaManager
from src.classifier import classify
from src.extractor import extract
from src.utils import (
    generate_doc_id,
    load_feedback,
    upsert_feedback,
)

# ───── page & globals ──────────────────────────────────────────────
st.set_page_config("Extraction", page_icon="🔍", layout="wide")
st.title("🔍 Extraction")
schema_mgr = SchemaManager()

# ───── sidebar: settings ───────────────────────────────────────────
with st.sidebar:
    st.header("⚙️  Options")
    run_ocr = st.checkbox("Run OCR first", value=False)
    ocr_engine = st.selectbox(
        "OCR engine", ["LLM-OCR", "Tesseract"], disabled=not run_ocr
    )

# ───── file uploader ────────────────────────────────────────────────
files = st.file_uploader(
    "Upload PDFs or images",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
)
if not files:
    st.info("Awaiting uploads …")
    st.stop()

# ───── load past corrections by filename ────────────────────────────
## CHANGE 1: Load not just the doc type, but also the previously corrected metadata.
past = load_feedback()
corrected_map = {}
past_metadata_map = {}
for r in past:
    if r.get("file_name"):
        corrected_map[r["file_name"]] = r["doc_type"]
        # Check for non-empty corrected metadata to load
        if r.get("metadata_corrected") and r["metadata_corrected"] != "{}":
            try:
                past_metadata_map[r["file_name"]] = json.loads(r["metadata_corrected"])
            except json.JSONDecodeError:
                # Gracefully handle if a line in the feedback file is malformed
                pass

# ───── ensure session state ────────────────────────────────────────
st.session_state.setdefault("doc_rows", [])
st.session_state.setdefault("extracted", False)
doc_rows: List[dict] = st.session_state["doc_rows"]

# ───── run buttons ─────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
seq_clicked = c1.button("🚀 Classify & Extract", use_container_width=True)
classify_clicked = c2.button("▶️ Classify Only", use_container_width=True)
extract_clicked = c3.button(
    "⚡ Extract All", disabled=not doc_rows, use_container_width=True
)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# ───── 1️⃣ on-click: build doc_rows ─────────────────────────────────
if classify_clicked or seq_clicked:
    st.session_state["extracted"] = False
    st.session_state["doc_rows"] = []
    prog = st.progress(0.0, "Classifying…")

    cls_results = []
    for i, up in enumerate(files, start=1):
        images = preprocess(up)
        fname = up.name
        doc_id = generate_doc_id(up) or f"id_{i}"

        with io.BytesIO() as buf:
            img = images[0].copy()
            img.thumbnail((140, 140))
            img.save(buf, format="PNG")
            thumb = buf.getvalue()

        if fname in corrected_map:
            doc_type = corrected_map[fname]
            reasoning = "retrieved from past correction"
            detected_type = None
        else:
            cls = classify(images, schema_mgr.get_types())
            doc_type = cls["doc_type"]
            detected_type = cls["doc_type"]
            reasoning = cls.get("reasoning", "")

        cls_results.append(
            {
                "file_name": fname,
                "doc_id": doc_id,
                "thumb": thumb,
                "images": images,
                "detected": detected_type,
                "final_type": doc_type,
                "reasoning": reasoning,
                "fields": None,
                "fields_corrected": None,
            }
        )
        prog.progress(i / len(files), f"Classifying: {fname}")

    st.session_state["doc_rows"] = cls_results
    doc_rows = st.session_state["doc_rows"]
    st.toast("Classification finished – adjust below if needed.", icon="✅")
    if not seq_clicked:
        st.rerun()

# ───── 2️⃣ render classification review ──────────────────────────────
if doc_rows and not st.session_state.get("extracted"):
    st.subheader("📑 Review detected document types")
    for idx, row in enumerate(doc_rows):
        with st.expander(f"{row['file_name']} — {row['final_type']}", expanded=False):
            img_col, sel_col = st.columns([1, 2])
            with img_col:
                st.image(row["thumb"], width=140)
            with sel_col:
                choices = schema_mgr.get_types()
                if row["final_type"] not in choices:
                    choices.insert(0, row["final_type"])
                sel = st.selectbox(
                    "Document type",
                    choices,
                    index=choices.index(row["final_type"]),
                    key=f"type_{row['doc_id']}",
                )
                st.session_state["doc_rows"][idx]["final_type"] = sel
    if st.button("💾 Save type corrections"):
        for row in doc_rows:
            upsert_feedback(
                {
                    "doc_id": row["doc_id"],
                    "file_name": row["file_name"],
                    "doc_type": row["final_type"],
                    "metadata_extracted": "{}",
                    "metadata_corrected": "{}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        st.toast("Document types saved 👍", icon="💾")

# ───── 3️⃣ ON-CLICK: run extraction ────────────────────────────────
if (extract_clicked or seq_clicked) and not st.session_state.get("extracted"):
    st.subheader("📦 Extracting Data...")
    prog = st.progress(0.0, "Extracting…")

    for i, row in enumerate(doc_rows, start=1):
        schema = schema_mgr.get(row["final_type"]) or []
        out = extract(row["images"], schema)

        # This stores the raw AI extraction result. It will NOT be changed by user edits.
        st.session_state["doc_rows"][i - 1]["fields"] = out["metadata"]

        ## CHANGE 2: If we have a past correction for this file, load it. Otherwise, use the new extraction.
        file_name = row["file_name"]
        if file_name in past_metadata_map:
            st.session_state["doc_rows"][i - 1]["fields_corrected"] = past_metadata_map[
                file_name
            ]
        else:
            st.session_state["doc_rows"][i - 1]["fields_corrected"] = out[
                "metadata"
            ].copy()

        prog.progress(i / len(doc_rows), f"Extracting from: {row['file_name']}")

    st.session_state["extracted"] = True
    st.toast("Extraction completed – review below", icon="📦")
    st.rerun()

# ───── 4️⃣ RENDER: extraction review & correction UI ────────────────
if st.session_state.get("extracted"):
    st.subheader("📦 Review and Correct Extracted Data")

    for i, row in enumerate(doc_rows):
        with st.expander(f"{row['file_name']} — {row['final_type']}", expanded=True):
            # The logic now depends on 'fields_corrected', which is the user-facing, editable data.
            if not row.get("fields_corrected"):
                st.warning("No fields were extracted or loaded for this document type.")
                continue

            ## CHANGE 3: Modify the UI to show a single editable column.
            # Create a DataFrame from 'fields_corrected' for the editable view.
            df = pd.DataFrame(
                {
                    "Field": list(row["fields_corrected"].keys()),
                    "Value": list(row["fields_corrected"].values()),
                }
            )

            edited_df = st.data_editor(
                df,
                key=f"grid_{row['doc_id']}",
                use_container_width=True,
                disabled=["Field"],  # Only disable the Field name column
            )

            # Convert the edited DataFrame back to a dictionary.
            updated_values = pd.Series(
                edited_df.Value.values, index=edited_df.Field
            ).to_dict()

            # Update the 'fields_corrected' in session state to persist edits across reruns.
            st.session_state["doc_rows"][i]["fields_corrected"] = updated_values

            if st.button("💾 Save this doc", key=f"save_{row['doc_id']}"):
                current_row = st.session_state["doc_rows"][i]
                upsert_feedback(
                    {
                        "doc_id": current_row["doc_id"],
                        "file_name": current_row["file_name"],
                        "doc_type": current_row["final_type"],
                        # Save the ORIGINAL extraction here
                        "metadata_extracted": json.dumps(
                            current_row["fields"], ensure_ascii=False
                        ),
                        # Save the FINAL (edited) values here
                        "metadata_corrected": json.dumps(
                            current_row["fields_corrected"], ensure_ascii=False
                        ),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                st.toast(f"Saved {current_row['file_name']}", icon="💾")

    if st.button("💾 Save all corrections", use_container_width=True, type="primary"):
        for row in st.session_state["doc_rows"]:
            upsert_feedback(
                {
                    "doc_id": row["doc_id"],
                    "file_name": row["file_name"],
                    "doc_type": row["final_type"],
                    "metadata_extracted": json.dumps(row["fields"], ensure_ascii=False),
                    "metadata_corrected": json.dumps(
                        row["fields_corrected"], ensure_ascii=False
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        st.toast("All feedback saved – thank you!", icon="💾")
