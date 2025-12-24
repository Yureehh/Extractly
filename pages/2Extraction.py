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
from utils.ui_components import inject_logo, inject_common_styles
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

inject_logo("data/assets/data_reply.svg", height="80px")  # Adjust height as needed
inject_common_styles()

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
    run_ocr_checkbox = st.checkbox("Run OCR first", value=False)
    calc_conf = st.checkbox("Compute confidences", value=False)
    conf_threshold = st.slider(
        "Confidence threshold (%)",
        0,
        100,
        70,
        help="Documents below this confidence will be flagged",
    )
    # NEW: System Prompts Section
    st.header("🤖 System Prompts")

    # Updated default prompts
    DEFAULT_CLASSIFIER_PROMPT = """You are an expert document classifier specialized in analyzing business and legal documents.
    Your task is to classify the document type based on visual layout, text content, headers, logos, and structural elements. Consider:
    - Document formatting and layout patterns
    - Official headers, letterheads, and logos
    - Specific terminology and field labels
    - Regulatory compliance markers
    - Standard document structures

    Respond with only the most accurate document type from the provided list. If unsure, choose "Unknown".
    """

    DEFAULT_EXTRACTOR_PROMPT = """You are a precise metadata extraction specialist. Your task is to extract specific field values from documents with high accuracy.

    Instructions:
    1. Analyze the document image carefully for text, tables, and structured data
    2. Extract only the exact values for the requested fields
    3. Use OCR context when provided to improve accuracy
    4. If a field is not clearly visible or readable, return null
    5. Maintain original formatting for dates, numbers, and codes
    6. For confidence scores, rate 0.0-1.0 based on text clarity and certainty

    Return valid JSON with three sections:
    - "metadata": field values as key-value pairs
    - "snippets": supporting text evidence for each field
    - "confidence": confidence scores (0.0-1.0) for each extraction
    """

    with st.expander("📝 Edit Prompts", expanded=False):
        st.subheader("Classification Prompt")
        classifier_prompt = st.text_area(
            "System prompt for document classification:",
            value=st.session_state.get("classifier_prompt", DEFAULT_CLASSIFIER_PROMPT),
            height=150,
            help="This prompt guides how the AI classifies document types",
            key="classifier_prompt_input",
        )

        st.subheader("Extraction Prompt")
        extractor_prompt = st.text_area(
            "System prompt for metadata extraction:",
            value=st.session_state.get("extractor_prompt", DEFAULT_EXTRACTOR_PROMPT),
            height=200,
            help="This prompt guides how the AI extracts metadata fields",
            key="extractor_prompt_input",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Prompts"):
                st.session_state["classifier_prompt"] = classifier_prompt
                st.session_state["extractor_prompt"] = extractor_prompt
                st.success("Prompts saved!")

        with col2:
            if st.button("🔄 Reset to Default"):
                st.session_state["classifier_prompt"] = DEFAULT_CLASSIFIER_PROMPT
                st.session_state["extractor_prompt"] = DEFAULT_EXTRACTOR_PROMPT
                st.rerun()

    # ✂︎────────────────────────  OCR-preview toggle  ──────────────────────✂︎
    if run_ocr_checkbox and "ocr_map" in st.session_state:
        with st.sidebar.expander("🔍 Preview raw OCR text", expanded=False):
            for name, ocr_txt in st.session_state["ocr_map"].items():
                st.markdown(f"**{name}**")
                st.text_area(
                    label=" ",
                    value=ocr_txt[:10_000],
                    height=200,
                    key=f"ocr_{name}",
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
past = load_feedback()
corrected_map = {}
past_metadata_map = {}
for r in past:
    if r.get("file_name"):
        corrected_map[r["file_name"]] = r["doc_type"]
        if r.get("metadata_corrected") and r["metadata_corrected"] != "{}":
            with contextlib.suppress(json.JSONDecodeError):
                past_metadata_map[r["file_name"]] = json.loads(r["metadata_corrected"])

# ───── ensure session state ────────────────────────────────────────
st.session_state.setdefault("doc_rows", [])
st.session_state.setdefault("extracted", False)
doc_rows: list[dict] = st.session_state["doc_rows"]

# ───── run buttons ─────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
seq_clicked = c1.button("🚀 Classify & Extract", width="stretch")
classify_clicked = c2.button("▶️ Classify Only", width="stretch")
extract_clicked = c3.button("⚡ Extract All", disabled=not doc_rows, width="stretch")

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

    # CHANGE: Add Unknown/Other to classification candidates
    classification_candidates = schema_mgr.get_types() + ["Unknown", "Other"]

    for i, up in enumerate(files, start=1):
        images = preprocess(up)
        fname = up.name
        doc_id = generate_doc_id(up) or f"id_{i}"
        ocr_txt = ""

        if run_ocr_checkbox:
            ocr_txt = run_ocr(images)  # Removed engine parameter - LLM only
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

        # ---------- build rows with enhanced classification -------------------------
        if fname in corrected_map:
            doc_type = corrected_map[fname]
            confidence = None
            reasoning = "retrieved from past correction"
        else:
            cls_resp = classify(
                images,
                classification_candidates,
                use_confidence=calc_conf,
                n_votes=5,
                system_prompt=st.session_state.get(
                    "classifier_prompt", DEFAULT_CLASSIFIER_PROMPT
                ),
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
        # CHANGE: Enhanced confidence display and unrecognized document handling
        confidence_val = row.get("confidence")
        conf_pct = int(confidence_val * 100) if confidence_val is not None else None
        is_unrecognized = row["final_type"] in ["Unknown", "Other"]
        is_low_confidence = conf_pct is not None and conf_pct < conf_threshold

        # Color-coded title based on status
        if is_unrecognized or is_low_confidence:
            status_emoji = "⚠️"
            title_color = "🔴"
        else:
            status_emoji = "✅"
            title_color = "🟢"

        # Build title with conditional confidence display
        if calc_conf and conf_pct is not None:
            title = f"{status_emoji} {row['file_name']} — {row['final_type']} {title_color} {conf_pct}%"
        else:
            title = f"{status_emoji} {row['file_name']} — {row['final_type']}"

        with st.expander(
            title,
            expanded=is_unrecognized
            or is_low_confidence,  # Auto-expand problematic ones
        ):
            col1, col2, col3 = st.columns([1, 2, 1])

            with col1:
                st.image(row["thumb"], width=140)

            with col2:
                # CHANGE: Enhanced type selection with Unknown/Other
                choices = schema_mgr.get_types() + ["Unknown", "Other"]
                if row["final_type"] not in choices:
                    choices.insert(0, row["final_type"])

                sel = st.selectbox(
                    "Document type",
                    choices,
                    index=choices.index(row["final_type"]),
                    key=f"type_{row['doc_id']}",
                )
                st.session_state["doc_rows"][idx]["final_type"] = sel

                # Enhanced status display
                if is_unrecognized:
                    st.error("❌ Unrecognized document type")
                elif is_low_confidence:
                    st.warning(f"⚠️ Low confidence ({conf_pct}% < {conf_threshold}%)")
            with col3:
                # CHANGE: Enhanced confidence display in % - only show if calc_conf is enabled
                if calc_conf and conf_pct is not None:
                    if conf_pct >= 80:
                        st.success(f"🟢 {conf_pct}%")
                    elif conf_pct >= 60:
                        st.warning(f"🟡 {conf_pct}%")
                    else:
                        st.error(f"🔴 {conf_pct}%")

                    st.caption(f"Threshold: {conf_threshold}%")
                elif calc_conf:
                    st.caption("Confidence not computed")

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

# ───── 3️⃣ ON-CLICK: run extraction with unrecognized document handling ────────────────
if (extract_clicked or seq_clicked) and not st.session_state.get("extracted"):
    st.subheader("📦 Extracting Data...")
    prog = st.progress(0.0, "Extracting…")

    for i, row in enumerate(doc_rows, start=1):
        if "cancel_extraction" in st.session_state:
            break

        # CHANGE: Skip extraction for unrecognized documents
        if row["final_type"] in ["Unknown", "Other"]:
            st.session_state["doc_rows"][i - 1]["fields"] = {}
            st.session_state["doc_rows"][i - 1]["field_conf"] = {}
            st.session_state["doc_rows"][i - 1]["fields_corrected"] = {}
            prog.progress(
                i / len(doc_rows), f"Skipping unrecognized: {row['file_name']}"
            )
            continue

        schema = schema_mgr.get(row["final_type"]) or []
        if not schema:
            st.session_state["doc_rows"][i - 1]["fields"] = {}
            st.session_state["doc_rows"][i - 1]["field_conf"] = {}
            st.session_state["doc_rows"][i - 1]["fields_corrected"] = {}
            continue

        ocr_txt = None
        if run_ocr_checkbox:
            ocr_txt = run_ocr(row["images"])  # Removed engine parameter - LLM only
        out = extract(
            row["images"],
            schema,
            ocr_text=ocr_txt,
            with_confidence=calc_conf,
            system_prompt=st.session_state.get(
                "extractor_prompt", DEFAULT_EXTRACTOR_PROMPT
            ),
        ) or {"metadata": {}, "confidence": {}}

        if not any(out["metadata"].values()):
            st.toast(f"No fields detected in {row['file_name']}", icon="⚠️")

        st.session_state["doc_rows"][i - 1]["fields"] = out["metadata"]
        st.session_state["doc_rows"][i - 1]["field_conf"] = out.get("confidence", {})

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
    extract_clicked = False
    seq_clicked = False
    st.toast("Extraction completed – review below", icon="📦")
    st.rerun()

# ───── 4️⃣ RENDER: extraction review & correction UI ────────────────
if st.session_state.get("extracted"):
    st.subheader("📦 Review and Correct Extracted Data")

    for i, row in enumerate(doc_rows):
        # CHANGE: Handle unrecognized documents in review
        if row["final_type"] in ["Unknown", "Other"]:
            with st.expander(
                f"⚠️ {row['file_name']} — {row['final_type']} (SKIPPED)", expanded=False
            ):
                st.warning(
                    "This document was skipped because it's unrecognized. Please reclassify it first."
                )
                continue

        with st.expander(f"{row['file_name']} — {row['final_type']}", expanded=True):
            if not row.get("fields_corrected"):
                st.warning("No fields were extracted or loaded for this document type.")
                continue

            # CHANGE: Enhanced confidence display in data editor (% format)
            row_conf = row.get("field_conf", {})
            # Convert confidence to percentage format
            conf_display = {}
            for k, v in row_conf.items():
                if isinstance(v, (int, float)):
                    conf_display[k] = f"{int(v * 100)}%"
                else:
                    conf_display[k] = str(v) if v else ""

            df = pd.DataFrame(
                {
                    "Field": list(row["fields_corrected"].keys()),
                    "Value": list(row["fields_corrected"].values()),
                    "Conf.": [
                        conf_display.get(k, "") for k in row["fields_corrected"]
                    ],  # CHANGE: Show %
                }
            )

            edited_df = st.data_editor(
                df,
                key=f"grid_{row['doc_id']}",
                disabled=["Field", "Conf."],
                width="stretch",
            )

            updated_values = pd.Series(
                edited_df.Value.values, index=edited_df.Field
            ).to_dict()

            st.session_state["doc_rows"][i]["fields_corrected"] = updated_values

            # ── enhanced action buttons ────────────────────────────────────
            col_re, col_save, col_download = st.columns([0.08, 0.08, 0.08])

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
                        system_prompt=st.session_state.get(
                            "extractor_prompt", DEFAULT_EXTRACTOR_PROMPT
                        ),
                    ) or {"metadata": {}, "confidence": {}}

                    row["fields"] = new_out["metadata"]
                    row["field_conf"] = new_out.get("confidence", {})
                    row["fields_corrected"] = new_out["metadata"].copy()
                    st.toast(f"Re-extracted {row['file_name']}", icon="✅")
                    st.rerun()

            with col_save:
                if st.button("💾 Save", key=f"save_{row['doc_id']}"):
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

            # NEW: Individual download button
            with col_download:
                if st.button("📄 JSON", key=f"download_{row['doc_id']}"):
                    # Fix: Handle None confidence properly
                    confidence_val = row.get("confidence")
                    if confidence_val is not None:
                        confidence_display = f"{int(confidence_val * 100)}%"
                    else:
                        confidence_display = "N/A"

                    result = {
                        "document_info": {
                            "filename": row["file_name"],
                            "document_type": row["final_type"],
                            "confidence": confidence_display,  # Fixed
                            "timestamp": datetime.now().isoformat(),
                        },
                        "original_extraction": row.get("fields", {}),
                        "corrected_metadata": row.get("fields_corrected", {}),
                        "confidence_scores": {
                            k: f"{int(v * 100)}%"
                            for k, v in row.get("field_conf", {}).items()
                            if isinstance(v, (int, float))
                            and v is not None  # Added None check
                        },
                        "processing_info": {
                            "ocr_used": run_ocr_checkbox,
                            "confidence_threshold": f"{conf_threshold}%",
                        },
                    }

    # Enhanced bulk save with session summary
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("💾 Save all corrections", width="stretch", type="primary"):
            saved_count = 0
            for row in st.session_state["doc_rows"]:
                if row["final_type"] not in ["Unknown", "Other"]:
                    upsert_feedback(
                        {
                            "doc_id": row["doc_id"],
                            "file_name": row["file_name"],
                            "doc_type": row["final_type"],
                            "metadata_extracted": json.dumps(
                                row["fields"], ensure_ascii=False
                            ),
                            "metadata_corrected": json.dumps(
                                row["fields_corrected"], ensure_ascii=False
                            ),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    saved_count += 1
            st.toast(f"Saved {saved_count} documents – thank you!", icon="💾")

    with col2:
        # NEW: Bulk download button
        if st.button("📥 Download All JSON", width="stretch"):
            # Prepare bulk export
            bulk_results = {
                "export_info": {
                    "timestamp": datetime.now().isoformat(),
                    "total_documents": len(doc_rows),
                    "processed_documents": len(
                        [
                            r
                            for r in doc_rows
                            if r["final_type"] not in ["Unknown", "Other"]
                        ]
                    ),
                    "confidence_threshold": f"{conf_threshold}%",
                },
                "documents": [],
            }

            for row in doc_rows:
                confidence_val = row.get("confidence")
                if confidence_val is not None:
                    confidence_display = f"{int(confidence_val * 100)}%"
                else:
                    confidence_display = "N/A"

                doc_result = {
                    "filename": row["file_name"],
                    "document_type": row["final_type"],
                    "confidence": confidence_display,  # Fixed
                    "original_extraction": row.get("fields", {}),
                    "corrected_metadata": row.get("fields_corrected", {}),
                    "confidence_scores": {
                        k: f"{int(v * 100)}%"
                        for k, v in row.get("field_conf", {}).items()
                        if isinstance(v, (int, float))
                        and v is not None  # Added None check
                    },
                }
                bulk_results["documents"].append(doc_result)

            json_str = json.dumps(bulk_results, indent=2, ensure_ascii=False)
            st.download_button(
                label="📄 Download Complete Session",
                data=json_str,
                file_name=f"bulk_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="bulk_download",
            )
