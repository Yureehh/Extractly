from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st
from PIL import Image

from src.config import load_config
from src.domain.run_store import RunStore
from src.domain.schema_store import SchemaStore
from src.integrations.preprocess import preprocess
from src.pipeline.classification import DEFAULT_CLASSIFIER_PROMPT
from src.pipeline.extraction import DEFAULT_EXTRACTION_PROMPT
from src.pipeline.runner import PipelineOptions, run_pipeline
from src.logging import setup_logging
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)


config = load_config()
setup_logging()
store = SchemaStore(config.prebuilt_schemas_path, config.custom_schemas_path)
run_store = RunStore(config.run_store_dir)

st.set_page_config(page_title="Extract", page_icon="⚡", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("⚡ Run Extraction")
st.caption("Upload documents and run the extraction pipeline.")

schemas = store.list_schemas()
if not schemas:
    st.warning("No schemas found. Create one in Schema Studio first.")
    st.stop()

schema_names = [schema.name for schema in schemas]

section_title("Schema routing")
schema_mode = st.radio(
    "Choose how documents are routed",
    options=["Classify documents", "Selected schemas"],
    index=0,
    horizontal=True,
)

section_spacer()

left, _, right = st.columns([5, 1, 4])
with left:
    files = st.file_uploader(
        "Upload documents",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True,
    )

with right:
    section_title("Pipeline options")
    compute_conf = st.toggle("Field confidence", value=True)
    enable_ocr = st.toggle("Enable OCR", value=False)
    st.caption("Runs multi-pass extraction across all pages for maximum accuracy.")

manual_overrides: dict[str, str] = {}
current_files: list[str] = []
if files:
    section_spacer()
    current_files = [upload.name for upload in files]
    if schema_mode == "Classify documents":
        section_title("Document routing overrides")
        st.caption(
            "Optionally assign a schema per document. Leave as Auto to classify normally."
        )
        default_choice = "Auto"
        options = ["Auto"] + schema_names
    else:
        section_title("Document schema selection")
        st.caption("Choose a schema for each document before running extraction.")
        default_choice = "Select schema"
        options = ["Select schema"] + schema_names

    if st.session_state.get("routing_files") != current_files:
        st.session_state["routing_files"] = current_files
        st.session_state.pop("routing_overrides", None)

    default_rows = [
        {"filename": filename, "document_type": default_choice}
        for filename in current_files
    ]
    routing_rows = st.data_editor(
        default_rows,
        num_rows="fixed",
        width="stretch",
        column_config={
            "filename": st.column_config.TextColumn("File", disabled=True),
            "document_type": st.column_config.SelectboxColumn(
                "Document type",
                options=options,
            ),
        },
        key="routing_overrides",
    )
    manual_overrides = {
        row["filename"]: row["document_type"]
        for row in routing_rows
        if row.get("document_type") not in (None, "", default_choice)
    }

with st.sidebar:
    st.subheader("Used prompts")
    with st.expander("Edit prompts", expanded=False):
        classifier_prompt = st.text_area(
            "Classifier prompt",
            value=st.session_state.get("classifier_prompt", DEFAULT_CLASSIFIER_PROMPT),
            height=140,
        )
        extractor_prompt = st.text_area(
            "Extraction prompt",
            value=st.session_state.get("extractor_prompt", DEFAULT_EXTRACTION_PROMPT),
            height=160,
        )
        if st.button("Save prompts"):
            st.session_state["classifier_prompt"] = classifier_prompt
            st.session_state["extractor_prompt"] = extractor_prompt
            st.success("Prompts saved.")

section_spacer("lg")

section_title("Pipeline preview")
if schema_mode == "Classify documents":
    steps = ["Parse", "Classify", "Extract", "Validate", "Export"]
else:
    steps = ["Parse", "Assign schemas", "Extract", "Validate", "Export"]

step_items: list[str] = []
for idx, step in enumerate(steps):
    step_items.append(f"<span class='extractly-stepper-item'>{step}</span>")
    if idx < len(steps) - 1:
        step_items.append("<span class='extractly-stepper-sep'>&rarr;</span>")

st.markdown(
    f"<div class='extractly-stepper'>{''.join(step_items)}</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='extractly-caption-space'>"
    "Preview updates automatically based on routing and per-file selections."
    "</div>",
    unsafe_allow_html=True,
)

if st.button("Run extraction", type="primary", width="stretch"):
    if not files:
        st.error("Upload at least one document.")
        st.stop()

    use_classification = schema_mode == "Classify documents"
    if not use_classification:
        missing = [
            filename for filename in current_files if filename not in manual_overrides
        ]
        if missing:
            st.error("Select a schema for each document before running.")
            st.stop()

    schema_map = {schema.name: schema for schema in schemas}
    parsed_files = []
    progress = st.progress(0.0, "Parsing files")

    for idx, upload in enumerate(files, start=1):
        filename = upload.name
        doc_type_override = manual_overrides.get(filename)

        if filename.lower().endswith(".txt"):
            content = upload.read().decode("utf-8", errors="ignore")
            blank_image = Image.new("RGB", (800, 1000), color="white")
            images = [blank_image]
            payload = {
                "name": filename,
                "images": images,
                "ocr_text": content,
            }
        else:
            images = preprocess(upload, filename)
            payload = {"name": filename, "images": images}

        if doc_type_override:
            payload["doc_type_override"] = doc_type_override
        parsed_files.append(payload)

        progress.progress(idx / len(files), f"Parsed {filename}")

    progress.empty()
    options = PipelineOptions(
        enable_ocr=enable_ocr,
        compute_confidence=compute_conf,
        classifier_prompt=st.session_state.get("classifier_prompt"),
        extraction_prompt=st.session_state.get("extractor_prompt"),
    )

    run_schema_name = "Classified" if use_classification else "Manual selection"
    progress = st.progress(0.0, "Starting pipeline...")

    def update_progress(label: str, value: float) -> None:
        progress.progress(value, label)

    run = run_pipeline(
        files=parsed_files,
        default_schema=None,
        schema_map=schema_map,
        candidates=schema_names + ["Unknown", "Other"],
        run_store=run_store,
        options=options,
        schema_name=run_schema_name,
        progress_callback=update_progress,
    )
    progress.empty()

    st.session_state["latest_run_id"] = run.run_id
    section_spacer()
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.success(f"Extraction completed • {completed_at}")
    st.page_link("pages/3_Results.py", label="View results", width="stretch")
