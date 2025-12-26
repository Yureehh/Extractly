from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st

from extractly.config import load_config
from extractly.domain.run_store import RunStore
from extractly.logging import setup_logging
from extractly.ui.components import inject_branding, inject_global_styles, section_title


config = load_config()
setup_logging()

st.set_page_config(page_title="Extractly", page_icon="✨", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

run_store = RunStore(config.run_store_dir)
runs = run_store.list_runs()

st.markdown(
    """
    <div class="extractly-hero">
        <h1>Extractly — Document Metadata Extraction Studio</h1>
        <p>Design schemas, classify incoming documents, and extract structured metadata in minutes. Built for
        client-ready demos with traceability, exports, and run history baked in.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

cta_cols = st.columns([1, 1, 2])
with cta_cols[0]:
    st.page_link("pages/1_Schema_Studio.py", label="🚀 Build a schema", use_container_width=True)
with cta_cols[1]:
    st.page_link("pages/2_Extract.py", label="⚡ Run extraction", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

section_title("How it works", "A streamlined workflow your clients understand in seconds.")
steps = st.columns(3)
steps[0].markdown(
    """
    <div class="extractly-step">
        <strong>Step A — Define a schema</strong>
        <p>Design fields, types, and requirements in Schema Studio or import JSON templates.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
steps[1].markdown(
    """
    <div class="extractly-step">
        <strong>Step B — Upload documents</strong>
        <p>Batch PDFs, images, or text. Enable OCR or fast mode depending on fidelity.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
steps[2].markdown(
    """
    <div class="extractly-step">
        <strong>Step C — Review results</strong>
        <p>View JSON, confidence scores, warnings, and exportable tables.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

section_title("Product highlights", "Purpose-built for metadata extraction teams and demos.")
features = st.columns(3)
features[0].markdown(
    """
    <div class="extractly-card">
        <h4>Schema Studio</h4>
        <p>Field editor, JSON preview, templates, and validation in one place.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
features[1].markdown(
    """
    <div class="extractly-card">
        <h4>Extraction Pipeline</h4>
        <p>Classification, extraction, validation, and export with transparent logs.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
features[2].markdown(
    """
    <div class="extractly-card">
        <h4>Run History</h4>
        <p>Every run is stored locally with artifacts for traceability and demos.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

section_title("Live workspace snapshot")
col_a, col_b, col_c = st.columns(3)
col_a.metric("Runs stored", len(runs))
latest_run = runs[0]["started_at"] if runs else "—"
col_b.metric("Latest run", latest_run)
col_c.metric("Schemas ready", len(list(config.schema_dir.glob("*.json"))))

st.markdown("---")

section_title("Demo flow")
st.write(
    "Use the sample schemas and documents shipped in the repo to walk through a full demo. "
    "Start in Schema Studio, then upload a sample document in Extract, and finish in Results."
)

sample_dir = config.sample_data_dir
if sample_dir.exists():
    samples = [p.name for p in sample_dir.glob("*.txt")]
    if samples:
        st.caption(f"Sample docs: {', '.join(samples)}")

st.info(
    "Need configuration? Visit Settings to review model choice, retries, and environment checks.",
    icon="⚙️",
)

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
