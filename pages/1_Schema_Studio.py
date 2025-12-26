from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from extractly.config import load_config
from extractly.domain.schema_store import SchemaStore, schemas_to_table, table_to_schema
from extractly.domain.validation import validate_schema
from extractly.logging import setup_logging
from extractly.ui.components import inject_branding, inject_global_styles, section_title


config = load_config()
setup_logging()
store = SchemaStore(config.schema_dir)

st.set_page_config(page_title="Schema Studio", page_icon="🧬", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("🧬 Schema Studio")
st.caption("Design, validate, and version schemas used in extraction runs.")

TEMPLATES = {
    "Invoice Lite": {
        "description": "Basic invoice metadata for demo flows.",
        "fields": [
            {"name": "Invoice Number", "type": "string", "required": True},
            {"name": "Invoice Date", "type": "date", "required": True},
            {"name": "Supplier", "type": "string", "required": True},
            {"name": "Total Amount", "type": "number", "required": True},
        ],
    },
    "Resume Snapshot": {
        "description": "Lightweight resume extraction fields.",
        "fields": [
            {"name": "Candidate Name", "type": "string", "required": True},
            {"name": "Primary Role", "type": "string", "required": True},
            {"name": "Years of Experience", "type": "integer"},
            {"name": "Location", "type": "string"},
        ],
    },
}

schemas = store.list_schemas()

with st.sidebar:
    st.subheader("Schemas")
    if schemas:
        selected_name = st.selectbox(
            "Choose schema",
            options=[schema.name for schema in schemas],
            index=0,
        )
    else:
        selected_name = None
        st.caption("No schemas yet. Create one below.")
    st.markdown("---")
    st.subheader("Templates")
    template_choice = st.selectbox("Load template", options=["—"] + list(TEMPLATES))
    if st.button("Use template", use_container_width=True):
        if template_choice != "—":
            template_payload = TEMPLATES[template_choice]
            st.session_state["schema_payload"] = {
                "name": template_choice,
                "description": template_payload["description"],
                "rows": template_payload["fields"],
            }
            st.rerun()

    st.markdown("---")
    st.subheader("Import / Export")
    upload = st.file_uploader("Import schema JSON", type=["json"])
    if upload:
        try:
            payload = json.load(upload)
            imported = store.import_payload(payload)
            st.success(f"Imported {len(imported)} schema(s).")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    if selected_name:
        schema = store.get_schema(selected_name)
        if schema:
            export_json = store.export_schema(schema)
            st.download_button(
                "Download schema JSON",
                data=export_json,
                file_name=f"{selected_name}.json",
                mime="application/json",
                use_container_width=True,
            )

    if selected_name and st.button("Delete schema", type="secondary", use_container_width=True):
        store.delete_schema(selected_name)
        st.success("Schema deleted.")
        st.rerun()

if schemas and selected_name:
    active_schema = store.get_schema(selected_name)
else:
    active_schema = None

payload = st.session_state.get(
    "schema_payload",
    {
        "name": active_schema.name if active_schema else "",
        "description": active_schema.description if active_schema else "",
        "rows": schemas_to_table(active_schema) if active_schema else [],
    },
)

section_title("Schema editor")
name = st.text_input("Schema name", value=payload.get("name", ""))
description = st.text_area("Description", value=payload.get("description", ""))

rows = payload.get("rows", [])

data = st.data_editor(
    rows,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "name": st.column_config.TextColumn("Field name", required=True),
        "type": st.column_config.SelectboxColumn(
            "Type",
            options=["string", "number", "integer", "boolean", "date", "enum", "object", "array"],
            required=True,
        ),
        "required": st.column_config.CheckboxColumn("Required"),
        "description": st.column_config.TextColumn("Description"),
        "example": st.column_config.TextColumn("Example"),
        "enum": st.column_config.TextColumn("Enum values (comma-separated)"),
    },
    key="schema_editor",
)

schema = table_to_schema(name=name, description=description, rows=data)
validation = validate_schema(schema)

col_a, col_b = st.columns([1, 1])
with col_a:
    if st.button("💾 Save schema", use_container_width=True):
        result = store.save_schema(schema)
        if result.is_valid:
            st.success("Schema saved.")
            st.session_state.pop("schema_payload", None)
            st.rerun()
        else:
            st.error("Schema failed validation. Fix errors below.")

with col_b:
    if st.button("Reset", use_container_width=True, type="secondary"):
        st.session_state.pop("schema_payload", None)
        st.rerun()

section_title("Validation")
if validation.errors:
    st.error("\n".join(validation.errors))
else:
    st.success("Schema is valid and ready for extraction.")

if validation.warnings:
    st.warning("\n".join(validation.warnings))

section_title("Live JSON preview")
st.code(store.export_schema(schema), language="json")
