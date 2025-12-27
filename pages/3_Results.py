from __future__ import annotations

import base64
import csv
import io
import json
from datetime import datetime, timezone
import html
from pathlib import Path
import streamlit as st

from src.config import load_config
from src.domain.run_store import RunStore
from src.logging import setup_logging
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)
from utils.utils import diff_fields, upsert_feedback


config = load_config()
setup_logging()
run_store = RunStore(config.run_store_dir)

st.set_page_config(page_title="Results", page_icon="📊", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("📊 Results")
st.caption("Browse extraction runs, review outputs, and export data.")

runs = run_store.list_runs()
if not runs:
    st.info("No runs yet. Run an extraction first.")
    st.stop()

run_ids = [run["run_id"] for run in runs]
latest_id = st.session_state.get("latest_run_id")
selected_id = st.selectbox(
    "Select a run",
    options=run_ids,
    index=run_ids.index(latest_id) if latest_id in run_ids else 0,
)

run = run_store.load(selected_id)
if not run:
    st.error("Run not found.")
    st.stop()

documents = run.get("documents", [])
if not documents:
    st.info("This run has no documents to display.")
    st.stop()

section_spacer("lg")
section_title("Run summary")
started_at_label = "—"
started_at = run.get("started_at")
if started_at:
    try:
        started_at_label = datetime.fromisoformat(started_at).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except ValueError:
        started_at_label = started_at

st.markdown(
    f"""
    <div class="extractly-meta-grid">
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Started</div>
            <div class="extractly-meta-value">{html.escape(started_at_label)}</div>
        </div>
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Schema</div>
            <div class="extractly-meta-value">{html.escape(str(run.get("schema_name", "—")))}</div>
        </div>
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Documents</div>
            <div class="extractly-meta-value">{len(documents)}</div>
        </div>
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Mode</div>
            <div class="extractly-meta-value">{html.escape(str(run.get("mode", "—")))}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

section_spacer("lg")

section_title("Documents")
review_threshold = st.slider(
    "Needs review threshold",
    min_value=0.0,
    max_value=1.0,
    value=0.6,
    step=0.05,
    help="Flags documents with low classification or field confidence.",
)
only_needs_review = st.checkbox("Show only needs review", value=False)
doc_rows = []
doc_rows.extend(
    (
        {
            "filename": doc.get("filename"),
            "document_type": (
                doc.get("document_type_corrected") or doc.get("document_type") or "—"
            ),
            "class_confidence": doc.get("confidence"),
            "review": "",
            "warnings": len(doc.get("warnings", [])),
            "errors": len(doc.get("errors", [])),
        }
    )
    for doc in documents
)
for row, doc in zip(doc_rows, documents):
    field_conf = doc.get("field_confidence", {}) or {}
    needs_review = any(
        isinstance(value, (int, float)) and value < review_threshold
        for value in field_conf.values()
    )
    class_conf = doc.get("confidence")
    if isinstance(class_conf, (int, float)) and class_conf < review_threshold:
        needs_review = True
    row["review"] = "⚠️ Needs review" if needs_review else ""

if only_needs_review:
    doc_rows = [row for row in doc_rows if row.get("review")]
st.dataframe(
    doc_rows,
    width="stretch",
    column_config={
        "filename": st.column_config.TextColumn("File", width="medium"),
        "document_type": st.column_config.TextColumn("Schema", width="small"),
        "class_confidence": st.column_config.NumberColumn("Class conf", width="small"),
        "review": st.column_config.TextColumn("Review", width="small"),
        "warnings": st.column_config.NumberColumn("Warnings", width="small"),
        "errors": st.column_config.NumberColumn("Errors", width="small"),
    },
)

section_spacer()
st.markdown(
    "<div class='extractly-detail-title'>View document details</div>",
    unsafe_allow_html=True,
)
selected_doc_name = st.selectbox(
    "Document",
    options=[doc["filename"] for doc in documents],
    label_visibility="collapsed",
)

selected_doc = next(
    (doc for doc in documents if doc["filename"] == selected_doc_name),
    None,
)

if selected_doc:
    preview_b64 = selected_doc.get("preview_image")
    if preview_b64:
        with st.expander("Document preview", expanded=True):
            st.image(
                base64.b64decode(preview_b64),
                width="stretch",
                caption=selected_doc_name,
            )
    else:
        st.caption("No preview available for this run.")

    doc_type_current = (
        selected_doc.get("document_type_corrected")
        or selected_doc.get("document_type")
        or ""
    )
    class_confidence = selected_doc.get("confidence")
    class_conf_label = (
        f"{class_confidence:.2f}" if isinstance(class_confidence, (int, float)) else "—"
    )

    st.markdown(
        "<div class='extractly-detail-subtitle'>Classification</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Confidence: {class_conf_label}")
    original_type = selected_doc.get("document_type_original") or selected_doc.get(
        "document_type"
    )
    if original_type and original_type != doc_type_current:
        st.caption(f"Original: {original_type}")

    corrected_payload = selected_doc.get("corrected") or selected_doc.get(
        "extracted", {}
    )
    field_confidence = selected_doc.get("field_confidence", {}) or {}
    low_conf_fields = [
        field
        for field, value in field_confidence.items()
        if isinstance(value, (int, float)) and value < review_threshold
    ]
    if low_conf_fields:
        st.caption("Low confidence: " + ", ".join(sorted(low_conf_fields)))

    field_rows = []
    for key, value in corrected_payload.items():
        confidence_value = field_confidence.get(key, "")
        status_label = ""
        if (
            isinstance(confidence_value, (int, float))
            and confidence_value < review_threshold
        ):
            status_label = "⚠️"
        field_rows.append(
            {
                "field": key,
                "value": value,
                "confidence": confidence_value,
                "status": status_label,
            }
        )

    with st.form(key=f"doc_corrections_{selected_doc_name}"):
        doc_type_input = st.text_input("Document type", value=doc_type_current)
        st.markdown(
            "<div class='extractly-detail-subtitle'>Extracted fields</div>",
            unsafe_allow_html=True,
        )
        edited_fields = st.data_editor(
            field_rows,
            num_rows="fixed",
            width="stretch",
            column_config={
                "field": st.column_config.TextColumn("Field", width="small"),
                "value": st.column_config.TextColumn("Value", width="large"),
                "confidence": st.column_config.NumberColumn(
                    "Confidence", width="small"
                ),
                "status": st.column_config.TextColumn("Flag", width="small"),
            },
            disabled=["field", "confidence", "status"],
            key=f"field_editor_{selected_doc_name}",
        )
        submitted = st.form_submit_button("Save corrections")

    if submitted:
        if hasattr(edited_fields, "to_dict"):
            edited_rows = edited_fields.to_dict("records")
        elif isinstance(edited_fields, dict):
            values = list(edited_fields.values())
            row_count = len(values[0]) if values else 0
            edited_rows = [
                {column: edited_fields[column][idx] for column in edited_fields}
                for idx in range(row_count)
            ]
        else:
            edited_rows = edited_fields or []

        corrected_map = {
            row.get("field"): row.get("value")
            for row in edited_rows
            if row.get("field")
        }

        original_extracted = selected_doc.get("extracted", {})
        selected_doc["document_type_original"] = selected_doc.get(
            "document_type_original", selected_doc.get("document_type")
        )
        selected_doc["document_type_corrected"] = (
            doc_type_input.strip() or selected_doc["document_type_original"]
        )
        selected_doc["document_type"] = selected_doc["document_type_corrected"]
        selected_doc["corrected"] = corrected_map
        run_store.update_run(selected_id, run)

        feedback_row = {
            "doc_id": f"{selected_id}:{selected_doc.get('filename')}",
            "run_id": selected_id,
            "filename": selected_doc.get("filename"),
            "schema_name": run.get("schema_name"),
            "document_type_original": selected_doc.get("document_type_original"),
            "document_type_corrected": selected_doc.get("document_type_corrected"),
            "extracted": original_extracted,
            "corrected": corrected_map,
            "changed_fields": diff_fields(original_extracted, corrected_map),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        upsert_feedback(feedback_row)
        st.success("Corrections saved.")
        st.rerun()

    if selected_doc.get("warnings"):
        st.warning("\n".join(selected_doc.get("warnings")))
    if selected_doc.get("errors"):
        st.error("\n".join(selected_doc.get("errors")))

section_spacer("lg")
section_title("Exports")

json_payload = json.dumps(run, indent=2, ensure_ascii=False)

st.download_button(
    "Download run JSON",
    data=json_payload,
    file_name=f"{selected_id}.json",
    mime="application/json",
)

csv_buffer = io.StringIO()
fieldnames = {
    "filename",
    "document_type",
    "document_type_original",
    "document_type_corrected",
    "confidence",
}
for doc in documents:
    fieldnames.update(doc.get("corrected", {}).keys())

writer = csv.DictWriter(csv_buffer, fieldnames=sorted(fieldnames))
writer.writeheader()
for doc in documents:
    doc_type_original = doc.get("document_type_original", doc.get("document_type"))
    doc_type_corrected = doc.get("document_type_corrected", doc.get("document_type"))
    row = {
        "filename": doc.get("filename"),
        "document_type": doc_type_corrected,
        "document_type_original": doc_type_original,
        "document_type_corrected": doc_type_corrected,
        "confidence": doc.get("confidence"),
    }
    row |= doc.get("corrected", {})
    writer.writerow(row)

st.download_button(
    "Download CSV",
    data=csv_buffer.getvalue(),
    file_name=f"{selected_id}.csv",
    mime="text/csv",
)
