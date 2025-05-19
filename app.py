import streamlit as st
import json
import os
import time
from utils.preprocess import preprocess
from utils.schema_manager import SchemaManager
from utils.classifier import classify
from utils.extractor import extract

# Page config
st.set_page_config(page_title="Universal Metadata Extractor", layout="wide")

# Top padding
st.markdown("<br><br>", unsafe_allow_html=True)

# Initialize schema manager and session state
schema_manager = SchemaManager()
if "custom_fields" not in st.session_state:
    st.session_state.custom_fields = []
if "custom_schemas" not in st.session_state:
    st.session_state.custom_schemas = {}
if "cls_resp" not in st.session_state:
    st.session_state.cls_resp = None
if "extraction_result" not in st.session_state:
    st.session_state.extraction_result = None
if "extraction_time" not in st.session_state:
    st.session_state.extraction_time = None

# Preload stored custom schemas
if st.session_state.custom_schemas:
    schema_manager.add_custom(st.session_state.custom_schemas)

# Sidebar: global settings and custom schemas
with st.sidebar:
    st.title("Settings")
    model_choice = st.selectbox(
        "LLM Model",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0
    )
    os.environ["CLASSIFY_MODEL"] = model_choice
    os.environ["EXTRACT_MODEL"] = model_choice

    st.markdown("---")
    st.header("Custom Schemas")
    st.write("Paste a JSON mapping of new doc-types to field lists:")
    placeholder = '''{
  "Passport": [
    {"name": "Passport Number", "description": "Unique passport ID."},
    {"name": "Full Name",         "description": "Holder’s full name."},
    {"name": "Nationality",       "description": "Citizenship country."}
  ]
}'''
    custom_json = st.text_area(
        "Custom schema JSON",
        height=150,
        placeholder=placeholder
    )
    if st.button("Load Custom Schemas"):
        try:
            custom = json.loads(custom_json)
            st.session_state.custom_schemas.update(custom)
            schema_manager.add_custom(custom)
            st.success("Loaded custom schemas.")
        except json.JSONDecodeError:
            st.error("Invalid JSON.")

# === 1. Document Input & Type Configuration ===
st.markdown("## 1. Document Input & Type Configuration")
st.markdown("<br>", unsafe_allow_html=True)
input_col, _, type_col = st.columns([2, 0.2, 2])

with input_col:
    st.subheader("Upload Document")
    uploaded_file = st.file_uploader(
        "PDF or image", type=["pdf", "png", "jpg", "jpeg"]
    )
    if uploaded_file:
        images = preprocess(uploaded_file)
        st.image(images[0], caption="Preview", use_container_width=True)

with type_col:
    st.subheader("Document Type Configuration")
    doc_types = schema_manager.get_types()

    mode = st.radio(
        "Mode",
        ["Auto-detect", "Specify Type"],
        index=0 if st.session_state.cls_resp is None else 1,
        key="mode"
    )

    if mode == "Auto-detect":
        st.caption("Optionally narrow the search by selecting some types.")
        potentials = st.multiselect("Potential types", options=doc_types)
        ctx = st.text_area(
            "Context (optional)",
            key="class_desc",
            height=80,
            placeholder="e.g. Invoices from Vendor X"
        )
        if st.button("Classify Document"):
            if not uploaded_file:
                st.error("Upload a document first.")
            else:
                cls = classify(images, potentials or doc_types)
                st.session_state.cls_resp = cls
                st.success(f"Detected type: {cls['doc_type']}")
                # clear the radio state so it switches to 'Specify Type'
                del st.session_state["mode"]
                st.rerun()
    else:
        default_idx = 0
        if st.session_state.cls_resp:
            dt = st.session_state.cls_resp.get("doc_type")
            if dt in doc_types:
                default_idx = doc_types.index(dt)
        selected = st.selectbox(
            "Select document type",
            options=doc_types,
            index=default_idx
        )

# spacer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")

# === 2. Metadata Schema Definition ===
st.markdown("## 2. Metadata Schema Definition")
st.write("Built-in fields auto-load; add or clear for custom schemas below.")
st.markdown("<br>", unsafe_allow_html=True)
left_col, _, right_col = st.columns([2, 0.2, 2])

active_type = selected if mode == "Specify Type" else (
    st.session_state.cls_resp and st.session_state.cls_resp.get("doc_type")
)

with left_col:
    st.markdown("**Fields to Extract:**")
    if st.session_state.custom_fields:
        for f in st.session_state.custom_fields:
            st.write(f"- **{f['name']}**: {f['description']}")
    elif active_type:
        fields = schema_manager.get(active_type) or []
        for f in fields:
            st.write(f"- **{f['name']}**: {f['description']}")
        st.session_state.custom_fields = fields.copy()
    else:
        st.info("No fields defined.")

with right_col:
    st.markdown("**Add New Field:**")
    fn = st.text_input("Field Name", key="new_field_name", placeholder="e.g. Invoice Number")
    fd = st.text_input("Field Description", key="new_field_desc", placeholder="e.g. Total Amount")
    if st.button("Add Field"):
        if fn and fd:
            st.session_state.custom_fields.append({"name": fn, "description": fd})
            st.success(f"Added field '{fn}'")
            st.rerun()
        else:
            st.error("Both name and description are required.")
    if st.session_state.custom_fields and st.button("Clear Fields"):
        st.session_state.custom_fields = []
        st.rerun()

# spacer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")

# === 3. Extraction & Results ===
st.markdown("## 3. Extraction & Results")
st.markdown("<br>", unsafe_allow_html=True)
extract_col, feedback_col = st.columns([1, 1])

with extract_col:
    st.subheader("Extract Metadata")
    if st.button("Run Extraction"):
        if not uploaded_file:
            st.error("Upload a document first.")
        elif not active_type:
            st.error("Specify or classify a document type first.")
        else:
            with st.spinner("Extracting…"):
                start = time.time()
                images = preprocess(uploaded_file)
                schema = st.session_state.custom_fields
                res = extract(images, schema)
                print(res)
                st.session_state.extraction_result = res
                st.session_state.extraction_time = time.time() - start

    if st.session_state.extraction_result:
        st.markdown(f"**Done in {st.session_state.extraction_time:.1f}s**")
        st.markdown("<br>", unsafe_allow_html=True)
        for k, v in st.session_state.extraction_result.get("metadata", {}).items():
            st.write(f"- **{k}**: {v}")

with feedback_col:
    st.subheader("Feedback")
    st.text_area("Leave notes or feedback here…", height=400)
