from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import streamlit as st

from extractly.config import load_config
from extractly.domain.run_store import RunStore
from extractly.logging import setup_logging
from extractly.ui.components import inject_branding, inject_global_styles, section_title


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

section_title("Run summary")
summary_cols = st.columns(4)
summary_cols[0].metric("Run ID", run["run_id"])
summary_cols[1].metric("Schema", run.get("schema_name", "—"))
summary_cols[2].metric("Mode", run.get("mode", "—"))
summary_cols[3].metric("Documents", len(run.get("documents", [])))

st.markdown("---")

section_title("Documents")
doc_rows = []
for doc in run.get("documents", []):
    doc_rows.append(
        {
            "filename": doc.get("filename"),
            "document_type": doc.get("document_type"),
            "confidence": doc.get("confidence"),
            "warnings": len(doc.get("warnings", [])),
            "errors": len(doc.get("errors", [])),
        }
    )

st.dataframe(doc_rows, use_container_width=True)

selected_doc_name = st.selectbox(
    "View document details",
    options=[doc["filename"] for doc in run.get("documents", [])],
)

selected_doc = next(
    (doc for doc in run.get("documents", []) if doc["filename"] == selected_doc_name),
    None,
)

if selected_doc:
    section_title("Extracted fields")
    field_rows = [
        {
            "field": key,
            "value": value,
            "confidence": selected_doc.get("field_confidence", {}).get(key, ""),
        }
        for key, value in selected_doc.get("corrected", {}).items()
    ]
    st.dataframe(field_rows, use_container_width=True)

    section_title("JSON output")
    st.json(selected_doc.get("corrected", {}))

    if selected_doc.get("warnings"):
        st.warning("\n".join(selected_doc.get("warnings")))
    if selected_doc.get("errors"):
        st.error("\n".join(selected_doc.get("errors")))

section_title("Exports")

json_payload = json.dumps(run, indent=2, ensure_ascii=False)

st.download_button(
    "Download run JSON",
    data=json_payload,
    file_name=f"{selected_id}.json",
    mime="application/json",
)

csv_buffer = io.StringIO()
fieldnames = {"filename", "document_type", "confidence"}
for doc in run.get("documents", []):
    fieldnames.update(doc.get("corrected", {}).keys())

writer = csv.DictWriter(csv_buffer, fieldnames=sorted(fieldnames))
writer.writeheader()
for doc in run.get("documents", []):
    row = {
        "filename": doc.get("filename"),
        "document_type": doc.get("document_type"),
        "confidence": doc.get("confidence"),
    }
    row.update(doc.get("corrected", {}))
    writer.writerow(row)

st.download_button(
    "Download CSV",
    data=csv_buffer.getvalue(),
    file_name=f"{selected_id}.csv",
    mime="text/csv",
)
