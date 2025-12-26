from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st
from PIL import Image

from extractly.config import load_config
from extractly.domain.run_store import RunStore
from extractly.domain.schema_store import SchemaStore
from extractly.integrations.preprocess import preprocess
from extractly.pipeline.classification import DEFAULT_CLASSIFIER_PROMPT
from extractly.pipeline.extraction import DEFAULT_EXTRACTION_PROMPT
from extractly.pipeline.runner import PipelineOptions, run_pipeline
from extractly.logging import setup_logging
from extractly.ui.components import inject_branding, inject_global_styles, section_title


config = load_config()
setup_logging()
store = SchemaStore(config.schema_dir)
run_store = RunStore(config.run_store_dir)

st.set_page_config(page_title="Extract", page_icon="⚡", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("⚡ Run Extraction")
st.caption("Upload documents, select a schema, and run the extraction pipeline.")

schemas = store.list_schemas()
if not schemas:
    st.warning("No schemas found. Create one in Schema Studio first.")
    st.stop()

schema_name = st.selectbox("Schema", options=[schema.name for schema in schemas])
active_schema = store.get_schema(schema_name)

left, right = st.columns([2, 1])
with left:
    files = st.file_uploader(
        "Upload documents",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True,
    )

with right:
    section_title("Pipeline options")
    enable_ocr = st.toggle("Enable OCR", value=False)
    compute_conf = st.toggle("Field confidence", value=True)
    mode = st.radio("Mode", options=["fast", "accurate"], horizontal=True)

with st.expander("Advanced prompts", expanded=False):
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

st.markdown("---")

section_title("Pipeline steps")
steps = st.columns(5)
steps[0].markdown("✅ 1. Parse")
steps[1].markdown("✅ 2. Classify")
steps[2].markdown("✅ 3. Extract")
steps[3].markdown("✅ 4. Validate")
steps[4].markdown("✅ 5. Export")

if st.button("Run extraction", type="primary", use_container_width=True):
    if not files:
        st.error("Upload at least one document.")
        st.stop()

    parsed_files = []
    progress = st.progress(0.0, "Parsing files")

    for idx, upload in enumerate(files, start=1):
        filename = upload.name
        if filename.lower().endswith(".txt"):
            content = upload.read().decode("utf-8", errors="ignore")
            blank_image = Image.new("RGB", (800, 1000), color="white")
            images = [blank_image]
            parsed_files.append(
                {
                    "name": filename,
                    "images": images,
                    "ocr_text": content,
                    "doc_type_override": active_schema.name,
                }
            )
        else:
            images = preprocess(upload, filename)
            parsed_files.append({"name": filename, "images": images})

        progress.progress(idx / len(files), f"Parsed {filename}")

    options = PipelineOptions(
        enable_ocr=enable_ocr,
        compute_confidence=compute_conf,
        mode=mode,
        classifier_prompt=st.session_state.get("classifier_prompt"),
        extraction_prompt=st.session_state.get("extractor_prompt"),
    )

    run = run_pipeline(
        files=parsed_files,
        schema=active_schema,
        candidates=[schema.name for schema in schemas] + ["Unknown", "Other"],
        run_store=run_store,
        options=options,
    )

    st.session_state["latest_run_id"] = run.run_id
    st.success("Extraction completed.")
    st.page_link("pages/3_Results.py", label="View results", use_container_width=True)

    st.caption(f"Run {run.run_id} stored at {config.run_store_dir}")
    st.code(f"Run completed at {datetime.now().isoformat()}")
