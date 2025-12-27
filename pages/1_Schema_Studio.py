# sourcery skip: hoist-if-from-if
from __future__ import annotations

import json
import pandas as pd
from pathlib import Path
import streamlit as st

from src.config import load_config
from src.domain.schema_store import SchemaStore, schemas_to_table, table_to_schema
from src.domain.validation import validate_schema
from src.integrations.ocr import run_ocr
from src.integrations.preprocess import preprocess
from src.logging import setup_logging
from src.pipeline.schema_suggest import suggest_schema_from_sample
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)


config = load_config()
setup_logging()
store = SchemaStore(config.prebuilt_schemas_path, config.custom_schemas_path)

st.set_page_config(page_title="Schema Studio", page_icon="🧬", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("🧬 Schema Studio")
st.caption("Design, validate, and version schemas used in extraction runs.")

schemas = store.list_schemas()
schema_map = {schema.name: schema for schema in schemas}
schema_names = sorted(schema_map)

with st.sidebar:
    st.subheader("Schemas")
    if schema_names:
        selected_name = st.selectbox(
            "Choose schema",
            options=schema_names,
            index=None,
            placeholder="Select a template",
        )
    else:
        selected_name = None
        st.caption("No templates yet. Upload a prebuilt schema to start.")
    previous_selection = st.session_state.get("schema_selector_prev")
    if selected_name != previous_selection:
        st.session_state["schema_selector_prev"] = selected_name
        selected_schema = schema_map.get(selected_name) if selected_name else None
        if selected_schema:
            st.session_state["schema_pending_update"] = {
                "payload": {
                    "name": selected_schema.name,
                    "description": selected_schema.description,
                    "rows": schemas_to_table(selected_schema),
                },
                "name": selected_schema.name,
                "description": selected_schema.description,
                "source": store.get_schema_source(selected_schema.name) or "custom",
                "original_name": selected_schema.name,
                "loaded_name": selected_schema.name,
            }
            st.rerun()

if "schema_payload" not in st.session_state:
    st.session_state["schema_payload"] = {"name": "", "description": "", "rows": []}
if "schema_editor_version" not in st.session_state:
    st.session_state["schema_editor_version"] = 0
if "loaded_schema_name" not in st.session_state:
    st.session_state["loaded_schema_name"] = None
if "schema_source" not in st.session_state:
    st.session_state["schema_source"] = "custom"
if "schema_original_name" not in st.session_state:
    st.session_state["schema_original_name"] = None

payload = st.session_state["schema_payload"]
if "schema_name_input" not in st.session_state:
    st.session_state["schema_name_input"] = payload.get("name", "")
if "schema_description_input" not in st.session_state:
    st.session_state["schema_description_input"] = payload.get("description", "")

pending_update = st.session_state.pop("schema_pending_update", None)
if pending_update:
    st.session_state["schema_payload"] = pending_update["payload"]
    st.session_state["schema_name_input"] = pending_update["name"]
    st.session_state["schema_description_input"] = pending_update["description"]
    st.session_state["schema_source"] = pending_update["source"]
    st.session_state["schema_original_name"] = pending_update["original_name"]
    st.session_state["loaded_schema_name"] = pending_update["loaded_name"]
    st.session_state["schema_editor_version"] = (
        st.session_state.get("schema_editor_version", 0) + 1
    )

name_value = st.session_state.get("schema_name_input", "")
normalized_name = name_value.strip()
existing_schema = schema_map.get(normalized_name) if normalized_name else None
loaded_name = st.session_state.get("loaded_schema_name")

if existing_schema and loaded_name != normalized_name:
    st.session_state["schema_payload"] = {
        "name": existing_schema.name,
        "description": existing_schema.description,
        "rows": schemas_to_table(existing_schema),
    }
    st.session_state["schema_name_input"] = existing_schema.name
    st.session_state["schema_description_input"] = existing_schema.description
    st.session_state["schema_source"] = (
        store.get_schema_source(existing_schema.name) or "custom"
    )
    st.session_state["schema_original_name"] = existing_schema.name
    st.session_state["loaded_schema_name"] = existing_schema.name
    st.session_state["schema_editor_version"] += 1
    st.rerun()

if not existing_schema and loaded_name is not None:
    st.session_state["schema_payload"] = {
        "name": normalized_name,
        "description": "",
        "rows": [],
    }
    st.session_state["schema_name_input"] = normalized_name
    st.session_state["schema_description_input"] = ""
    st.session_state["schema_source"] = "custom"
    st.session_state["schema_original_name"] = None
    st.session_state["loaded_schema_name"] = None
    st.session_state["schema_editor_version"] += 1
    st.rerun()

section_title("Schema details")
st.caption("Name and describe the schema used to guide extraction.")
name = st.text_input(
    "Schema name", key="schema_name_input", placeholder="e.g., Invoice"
)
description = st.text_area("Description", key="schema_description_input", height=120)

normalized_name = name.strip()

if normalized_name:
    loaded_label = st.session_state.get("loaded_schema_name")
    if loaded_label:
        source_label = st.session_state.get("schema_source") or "custom"
        st.caption(
            f"Loaded {source_label} schema: {loaded_label}. Rename to start fresh."
        )
    else:
        st.caption("No matching schema found. You're editing a new schema draft.")

payload = st.session_state["schema_payload"]
rows = payload.get("rows", [])
if hasattr(rows, "empty"):
    has_rows = not rows.empty
elif isinstance(rows, dict):
    has_rows = any(len(value) for value in rows.values())
else:
    has_rows = bool(rows)

editor_rows = (
    rows
    if has_rows
    else pd.DataFrame(
        {
            "name": pd.Series(dtype="str"),
            "type": pd.Series(dtype="str"),
            "required": pd.Series(dtype="bool"),
            "description": pd.Series(dtype="str"),
            "example": pd.Series(dtype="str"),
            "enum": pd.Series(dtype="str"),
        }
    )
)

section_spacer("lg")
section_title("Field editor")
editor_key = f"schema_editor_{st.session_state.get('schema_editor_version', 0)}"
data = st.data_editor(
    editor_rows,
    num_rows="dynamic",
    width="stretch",
    column_config={
        "name": st.column_config.TextColumn("Field name", required=True),
        "type": st.column_config.SelectboxColumn(
            "Type",
            options=[
                "string",
                "number",
                "integer",
                "boolean",
                "date",
                "enum",
                "object",
                "array",
            ],
            required=True,
        ),
        "required": st.column_config.CheckboxColumn("Required"),
        "description": st.column_config.TextColumn("Description"),
        "example": st.column_config.TextColumn("Example"),
        "enum": st.column_config.TextColumn("Enum values (comma-separated)"),
    },
    key=editor_key,
)

if hasattr(data, "to_dict"):
    normalized_rows = data.to_dict("records")
elif isinstance(data, list):
    normalized_rows = data
elif isinstance(data, dict):
    values = list(data.values())
    row_count = len(values[0]) if values else 0
    normalized_rows = [
        {column: data[column][idx] for column in data} for idx in range(row_count)
    ]
else:
    normalized_rows = list(data) if data else []

st.session_state["schema_payload"] = {
    "name": normalized_name,
    "description": description,
    "rows": normalized_rows,
}

schema = table_to_schema(
    name=normalized_name, description=description, rows=normalized_rows
)
validation = validate_schema(schema)

summary_cols = st.columns(3)
summary_cols[0].metric("Fields", len(schema.fields))
summary_cols[1].metric("Required", sum(field.required for field in schema.fields))
summary_cols[2].metric(
    "Enums",
    sum(field.field_type == "enum" for field in schema.fields),
)

section_spacer("lg")
col_a, col_b = st.columns([1, 1])
with col_a:
    if st.button("💾 Save schema", width="stretch"):
        result = store.save_schema(
            schema,
            source=st.session_state.get("schema_source"),
            original_name=st.session_state.get("schema_original_name"),
        )
        if result.is_valid:
            st.success("Schema saved.")
            st.session_state["schema_payload"] = {
                "name": schema.name,
                "description": schema.description,
                "rows": schemas_to_table(schema),
            }
            st.session_state["schema_source"] = (
                store.get_schema_source(schema.name) or "custom"
            )
            st.session_state["schema_original_name"] = schema.name
            st.session_state["loaded_schema_name"] = schema.name
            st.rerun()
        else:
            st.error("Schema failed validation. Fix errors below.")

with col_b:
    if st.button(
        "Discard changes",
        width="stretch",
        type="secondary",
        help="Clear edits and reload the last saved schema.",
    ):
        loaded_name = st.session_state.get("loaded_schema_name")
        if loaded_name:
            stored = store.get_schema(loaded_name)
            if stored:
                pending_payload = {
                    "name": stored.name,
                    "description": stored.description,
                    "rows": schemas_to_table(stored),
                }
                pending_name = stored.name
                pending_description = stored.description
                pending_source = store.get_schema_source(loaded_name) or "custom"
                pending_original_name = loaded_name
                pending_loaded_name = loaded_name
            else:
                pending_payload = {
                    "name": "",
                    "description": "",
                    "rows": [],
                }
                pending_name = ""
                pending_description = ""
                pending_source = "custom"
                pending_original_name = None
                pending_loaded_name = None
        else:
            pending_payload = {
                "name": "",
                "description": "",
                "rows": [],
            }
            pending_name = ""
            pending_description = ""
            pending_source = "custom"
            pending_original_name = None
            pending_loaded_name = None
        st.session_state["schema_pending_update"] = {
            "payload": pending_payload,
            "name": pending_name,
            "description": pending_description,
            "source": pending_source,
            "original_name": pending_original_name,
            "loaded_name": pending_loaded_name,
        }
        st.rerun()

st.caption(
    "Discard changes reloads the stored schema or clears the editor when starting fresh."
)

with st.sidebar:
    st.download_button(
        "Download schema JSON",
        data=store.export_schema(schema),
        file_name=f"{normalized_name or 'schema'}.json",
        mime="application/json",
        width="stretch",
        disabled=not bool(normalized_name),
    )

    delete_target = st.session_state.get("loaded_schema_name")
    if (
        st.button(
            "Delete schema",
            type="secondary",
            width="stretch",
            disabled=delete_target is None,
        )
        and delete_target
    ):
        store.delete_schema(delete_target)
        st.success("Schema deleted.")
        st.session_state["schema_pending_update"] = {
            "payload": {"name": "", "description": "", "rows": []},
            "name": "",
            "description": "",
            "source": "custom",
            "original_name": None,
            "loaded_name": None,
        }
        st.rerun()

    st.markdown("---")
    st.subheader("Generate from sample")
    sample = st.file_uploader(
        "Upload a sample document",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        key="schema_sample_upload",
    )
    use_ocr = st.toggle("Use OCR assist", value=True, key="schema_sample_ocr")
    if st.button(
        "Generate schema draft",
        width="stretch",
        disabled=sample is None,
    ):
        if not sample:
            st.error("Upload a sample document first.")
        else:
            with st.spinner("Generating schema draft..."):
                images = []
                ocr_text = None
                if sample.name.lower().endswith(".txt"):
                    ocr_text = sample.read().decode("utf-8", errors="ignore")
                else:
                    images = preprocess(sample, sample.name)
                    if use_ocr:
                        ocr_text = run_ocr(images)

                suggested = suggest_schema_from_sample(
                    images=images,
                    ocr_text=ocr_text,
                    sample_name=sample.name if sample else None,
                )
                raw_fields = (
                    suggested.get("fields", []) if isinstance(suggested, dict) else []
                )
                if not isinstance(raw_fields, list):
                    raw_fields = []
                rows = []
                for field in raw_fields:
                    enum_values = field.get("enum", field.get("enum_values", [])) or []
                    rows.append(
                        {
                            "name": field.get("name", ""),
                            "type": field.get(
                                "type", field.get("field_type", "string")
                            ),
                            "required": bool(field.get("required", False)),
                            "description": field.get("description", ""),
                            "example": field.get("example", ""),
                            "enum": ", ".join(enum_values),
                        }
                    )

                st.session_state["schema_pending_update"] = {
                    "payload": {
                        "name": suggested.get("name", "")
                        if isinstance(suggested, dict)
                        else "",
                        "description": suggested.get("description", "")
                        if isinstance(suggested, dict)
                        else "",
                        "rows": rows,
                    },
                    "name": suggested.get("name", "")
                    if isinstance(suggested, dict)
                    else "",
                    "description": suggested.get("description", "")
                    if isinstance(suggested, dict)
                    else "",
                    "source": "custom",
                    "original_name": None,
                    "loaded_name": None,
                }
                st.rerun()

    st.markdown("---")
    st.subheader("Prebuilt schemas")
    upload = st.file_uploader("Upload prebuilt schema JSON", type=["json"])
    if upload:
        try:
            payload = json.load(upload)
            imported = store.import_prebuilt_payload(payload)
            st.success(f"Imported {len(imported)} schema(s) into prebuilt.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")
    st.caption("Use the name field to load an existing schema or start a new one.")

if validation.errors or validation.warnings:
    section_spacer()
    section_title("Validation")
    st.caption("Checks schema name, field types, duplicates, and enum values.")
    if validation.errors:
        st.error("\n".join(validation.errors))
    if validation.warnings:
        st.warning("\n".join(validation.warnings))

section_spacer("lg")
section_title("Live JSON preview")
st.code(store.export_schema(schema), language="json")
