from __future__ import annotations

import json
import textwrap
from pathlib import Path
import pandas as pd
import streamlit as st

from src.config import load_config
from src.logging import setup_logging
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)
from utils.utils import load_feedback


config = load_config()
setup_logging()

st.set_page_config(page_title="Feedback", page_icon="📝", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("📝 Feedback")
st.caption("Review corrections captured from client edits and export training data.")


def _compact_value(value, limit: int = 140) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return textwrap.shorten(text, width=limit, placeholder="...")


def _build_diff_rows(original: dict, corrected: dict) -> list[dict]:
    rows = []
    all_fields = sorted(set(original) | set(corrected))
    for field in all_fields:
        original_value = original.get(field)
        corrected_value = corrected.get(field)
        if field not in original:
            status = "added"
        elif field not in corrected:
            status = "removed"
        elif original_value != corrected_value:
            status = "updated"
        else:
            status = "same"
        rows.append(
            {
                "field": field,
                "original": _compact_value(original_value),
                "corrected": _compact_value(corrected_value),
                "status": status,
            }
        )
    return rows


rows = load_feedback()
if not rows:
    st.info("No feedback captured yet.")
    st.stop()

unique_docs = {row.get("doc_id") for row in rows if row.get("doc_id")}
changed_fields_total = sum(len(row.get("changed_fields", [])) for row in rows)

section_title("Snapshot")
metrics = st.columns(3)
metrics[0].metric("Corrections", len(rows))
metrics[1].metric("Docs touched", len(unique_docs))
metrics[2].metric("Fields corrected", changed_fields_total)

section_spacer()
section_title("Corrections")

table_rows = []
for row in rows:
    table_rows.append(
        {
            "timestamp": row.get("timestamp"),
            "filename": row.get("filename"),
            "schema": row.get("schema_name"),
            "doc_type": row.get("document_type_corrected"),
            "fields": ", ".join(row.get("changed_fields", [])),
        }
    )

df = pd.DataFrame(table_rows)
st.dataframe(df, width="stretch")

section_spacer()
detail_options = [
    row.get("doc_id", f"row-{idx}") for idx, row in enumerate(rows, start=1)
]
selected_id = st.selectbox("View correction detail", options=detail_options)
selected_row = next(
    (row for row in rows if row.get("doc_id") == selected_id),
    rows[0],
)
original = selected_row.get("extracted", {}) or {}
corrected = selected_row.get("corrected", {}) or {}

section_title("Before/After diff")
show_changed_only = st.checkbox(
    "Show only changed fields",
    value=True,
    key=f"diff_only_{selected_id}",
)
diff_rows = _build_diff_rows(original, corrected)
if show_changed_only:
    diff_rows = [row for row in diff_rows if row["status"] != "same"]

if diff_rows:
    st.dataframe(
        diff_rows,
        width="stretch",
        column_config={
            "field": st.column_config.TextColumn("Field", width="small"),
            "original": st.column_config.TextColumn("Before", width="large"),
            "corrected": st.column_config.TextColumn("After", width="large"),
            "status": st.column_config.TextColumn("Status", width="small"),
        },
    )
else:
    st.caption("No field changes captured for this correction.")

with st.expander("Raw correction payload"):
    st.json(selected_row)

section_spacer()
section_title("Export")
jsonl_payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
st.download_button(
    "Download feedback JSONL",
    data=jsonl_payload,
    file_name="feedback.jsonl",
    mime="application/jsonl",
)
