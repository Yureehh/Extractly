from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st

from src.config import load_config
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)
from src.logging import setup_logging


config = load_config()
setup_logging()

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("⚙️ Settings")
st.caption("Review configuration, models, and environment status.")

section_title("🔐 Environment")
cols = st.columns(3)
cols[0].metric("OpenAI key", "✅ Found" if config.openai_api_key else "❌ Missing")
cols[1].metric("Timeout (s)", config.request_timeout_s)
cols[2].metric("Max retries", config.max_retries)

section_spacer("lg")
section_title("🧠 Models")
model_cols = st.columns(3)
model_cols[0].text_input("Classifier model", value=config.classify_model, disabled=True)
model_cols[1].text_input("Extractor model", value=config.extract_model, disabled=True)
model_cols[2].text_input("OCR model", value=config.ocr_model, disabled=True)

section_spacer("lg")
section_title("📁 Directories")
st.write(f"Prebuilt schemas: `{config.prebuilt_schemas_path}`")
st.write(f"Custom schemas: `{config.custom_schemas_path}`")
st.write(f"Runs: `{config.run_store_dir}`")

section_spacer("lg")
section_title("📝 Notes")
st.info(
    "To update models or pipeline settings, set the environment variables in your `.env` file. "
    "Run `streamlit run Home.py` after changing them.",
    icon="📝",
)

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
