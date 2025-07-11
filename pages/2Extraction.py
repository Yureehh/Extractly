"""
Batch Extraction – multi-doc classification, OCR, extraction & correction UI.
"""

from __future__ import annotations
import contextlib
import io
import json
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

from src.ocr_engine import run_ocr
from utils.preprocess import preprocess
from src.schema_manager import SchemaManager
from src.classifier import classify
from src.extractor import extract
from utils.utils import (
    generate_doc_id,
    load_feedback,
    upsert_feedback,
    diff_fields,
)

# ───── page & globals ──────────────────────────────────────────────
st.set_page_config("Extraction", page_icon="🔍", layout="wide")
st.title("🔍 Extraction")
schema_mgr = SchemaManager()

# ───── CSS for image hover zoom ────────────────────────────────────
st.markdown(
    """
<style>
img:hover { transform:scale(2.5); transition:0.15s ease-in-out;
            z-index:1000; position:relative }
</style>
""",
    unsafe_allow_html=True,
)

# ───── sidebar: settings ───────────────────────────────────────────
with st.sidebar:
    st.header("⚙️  Options")
    calc_conf = st.checkbox("Compute confidences", value=False)
    run_ocr_checkbox = st.checkbox("Run OCR first", value=False)
    ocr_engine = st.selectbox(
        "OCR engine",
        ["LLM-OCR", "Tesseract"],
        disabled=not run_ocr_checkbox,
        key="sel_engine",
    )

    # ✂︎────────────────────────  OCR-preview toggle  ──────────────────────✂︎
    if run_ocr_checkbox and "ocr_map" in st.session_state:
        with st.sidebar.expander("🔍 Preview raw OCR text", expanded=False):
            for name, ocr_txt in st.session_state["ocr_map"].items():
                st.markdown(f"**{name}**")
                st.text_area(
                    label=" ",  # blanks out
                    value=ocr_txt[:10_000],  # haven’t changed your 10 kB clamp
                    height=200,
                    key=f"ocr_{name}",  # unique key per file
                    label_visibility="collapsed",
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
            with contextlib.suppress(json.JSONDecodeError):
                past_metadata_map[r["file_name"]] = json.loads(r["metadata_corrected"])
# ───── ensure session state ────────────────────────────────────────
st.session_state.setdefault("doc_rows", [])
st.session_state.setdefault("extracted", False)
doc_rows: list[dict] = st.session_state["doc_rows"]

# ───── run buttons ─────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
seq_clicked = c1.button("🚀 Classify & Extract", use_container_width=True)
classify_clicked = c2.button("▶️ Classify Only", use_container_width=True)
extract_clicked = c3.button(
    "⚡ Extract All", disabled=not doc_rows, use_container_width=True
)

if st.button("🔄 Start over (keep uploads)", key="reset_all", type="secondary"):
    for k in ("doc_rows", "extracted", "ocr_map", "ocr_preview"):
        st.session_state.pop(k, None)
    st.toast("Workspace cleared – you can run the pipeline again.", icon="🔄")
    st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ───── 1️⃣ on-click: build doc_rows ─────────────────────────────────
if classify_clicked or seq_clicked:
    st.session_state["extracted"] = False
    st.session_state["ocr_preview"] = ""
    st.session_state["doc_rows"] = []
    prog = st.progress(0.0, "Classifying…")

    cls_results = []
    for i, up in enumerate(files, start=1):
        images = preprocess(up)
        fname = up.name
        doc_id = generate_doc_id(up) or f"id_{i}"

        ocr_txt = ""
        if run_ocr_checkbox:
            ocr_engine_name = "Paddle" if ocr_engine == "LLM-OCR" else "Tesseract"
            ocr_txt = run_ocr(images, ocr_engine_name)

            # keep a dict keyed by filename
            st.session_state.setdefault("ocr_map", {})
            st.session_state["ocr_map"][fname] = ocr_txt

            if (
                "ocr_preview" in st.session_state
                and not st.session_state["ocr_preview"]
            ):
                st.session_state["ocr_preview"] = ocr_txt

        with io.BytesIO() as buf:
            img = images[0].copy()
            img.thumbnail((140, 140))
            img.save(buf, format="PNG")
            thumb = buf.getvalue()

        # ---------- build rows  -------------------------
        if fname in corrected_map:
            doc_type = corrected_map[fname]
            confidence = None
            reasoning = "retrieved from past correction"
        else:
            cls_resp = classify(
                images,
                schema_mgr.get_types(),
                use_confidence=calc_conf,  # existing flag
                n_votes=5,  # or any number you like
            )
            doc_type = cls_resp["doc_type"]
            confidence = cls_resp.get("confidence")
            reasoning = cls_resp.get("reasoning", "")

        cls_results.append(
            {
                "file_name": fname,
                "doc_id": doc_id,
                "thumb": thumb,
                "images": images,
                "detected": doc_type,
                "final_type": doc_type,
                "reasoning": reasoning,
                "fields": None,
                "fields_corrected": None,
                "confidence": confidence,
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
        with st.expander(
            f"{row['file_name']} — {row['final_type']}",
            expanded=st.session_state.get("exp_open", True),
        ):
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
                if calc_conf and row.get("confidence") is not None:
                    st.caption(f"Original type select: {sel}.")
                    st.caption(f"Conf ≈ {row['confidence']:.0%}")
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

st.markdown("<br><br>", unsafe_allow_html=True)

# ───── 3️⃣ ON-CLICK: run extraction ────────────────────────────────
if (extract_clicked or seq_clicked) and not st.session_state.get("extracted"):
    st.subheader("📦 Extracting Data...")
    prog = st.progress(0.0, "Extracting…")

    for i, row in enumerate(doc_rows, start=1):
        if "cancel_extraction" in st.session_state:
            break

        schema = schema_mgr.get(row["final_type"]) or []
        if not schema:
            continue

        ocr_txt = None
        if run_ocr_checkbox:
            engine_name = "Paddle" if ocr_engine == "LLM-OCR" else "Tesseract"
            ocr_txt = run_ocr(row["images"], engine_name)

        # ---------- run extraction ---------------------
        out = extract(
            row["images"], schema, ocr_text=ocr_txt, with_confidence=calc_conf
        ) or {"metadata": {}, "confidence": {}}  # ← safeguard
        if not any(out["metadata"].values()):
            st.toast(f"No fields detected in {row['file_name']}", icon="⚠️")

        # This stores the raw AI extraction result. It will NOT be changed by user edits.
        st.session_state["doc_rows"][i - 1]["fields"] = out["metadata"]
        st.session_state["doc_rows"][i - 1]["field_conf"] = out.get("confidence", {})

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

    if st.session_state.get("extracted") is False:
        st.button("🛑 Cancel extraction", key="cancel_extraction")
    st.session_state["extracted"] = True
    extract_clicked = False  # prevent accidental re-entry on rerun
    seq_clicked = False
    st.toast("Extraction completed – review below", icon="📦")
    st.rerun()

# ───── 4️⃣ RENDER: extraction review & correction UI ────────────────
if st.session_state.get("extracted"):
    st.subheader("📦 Review and Correct Extracted Data")

    for i, row in enumerate(doc_rows):
        with st.expander(f"{row['file_name']} — {row['final_type']}", expanded=True):
            # ── skip rows that have not been extracted ──────────────────────
            if not row.get("fields_corrected"):
                st.warning("No fields were extracted or loaded for this document type.")
                continue

            # ── editable grid ───────────────────────────────────────────────
            row_conf = row.get("field_conf", {})
            df = pd.DataFrame(
                {
                    "Field": list(row["fields_corrected"].keys()),
                    "Value": list(row["fields_corrected"].values()),
                    "Conf.": [row_conf.get(k, "") for k in row["fields_corrected"]],
                }
            )
            edited_df = st.data_editor(
                df,
                key=f"grid_{row['doc_id']}",
                disabled=["Field", "Conf."],
                use_container_width=True,
            )
            st.session_state["doc_rows"][i]["fields_corrected"] = dict(
                zip(edited_df.Field, edited_df.Value)
            )

            # Convert the edited DataFrame back to a dictionary.
            updated_values = pd.Series(
                edited_df.Value.values, index=edited_df.Field
            ).to_dict()

            # Update the 'fields_corrected' in session state to persist edits across reruns.
            st.session_state["doc_rows"][i]["fields_corrected"] = updated_values

            # ── one-click re-extract & save buttons on one row ────────────────
            col_re, col_save, _ = st.columns([0.08, 0.08, 0.95])

            # ── one-click re-extract  ▸  always shown *before* Save button ──
            with col_re:
                if st.button("↻ Re-extract", key=f"reextract_{row['doc_id']}"):
                    schema = schema_mgr.get(row["final_type"]) or []
                    ocr_txt = (
                        st.session_state.get("ocr_map", {}).get(row["file_name"])
                        if run_ocr_checkbox
                        else None
                    )
                    new_out = extract(
                        row["images"],
                        schema,
                        ocr_text=ocr_txt,
                        with_confidence=calc_conf,
                    ) or {"metadata": {}, "confidence": {}}

                    # overwrite the row in-place
                    row["fields"] = new_out["metadata"]
                    row["field_conf"] = new_out.get("confidence", {})
                    row["fields_corrected"] = new_out["metadata"].copy()
                    st.toast(f"Re-extracted {row['file_name']}", icon="✅")
                    st.rerun()  # show fresh values immediately

            # ── save button ───────────────────────────────────────────────
            with col_save:
                if st.button("💾 Save this doc", key=f"save_{row['doc_id']}"):
                    current_row = st.session_state["doc_rows"][i]
                    changed = diff_fields(
                        current_row["fields"], current_row["fields_corrected"]
                    )
                    upsert_feedback(
                        {
                            "doc_id": current_row["doc_id"],
                            "file_name": current_row["file_name"],
                            "doc_type": current_row["final_type"],
                            "metadata_extracted": json.dumps(
                                current_row["fields"], ensure_ascii=False
                            ),
                            "metadata_corrected": json.dumps(
                                current_row["fields_corrected"], ensure_ascii=False
                            ),
                            "fields_corrected": changed,
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
