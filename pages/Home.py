"""
Landing page – hero header + live stats (no quick-link buttons).
"""
import streamlit as st
from pathlib import Path
from datetime import datetime
from src.utils import load_feedback          # <-- utils lives in /src

st.set_page_config(
    page_title="Universal Metadata Extractor",
    page_icon="📄",
    layout="wide"
)

# ---------- 🎨  hero + CSS ----------
st.markdown(
    """
    <style>
      .hero   {text-align:center;margin-top:3rem;margin-bottom:2rem;}
      .hero h1{font-size:3rem;}
      .metric {padding:1rem;border-radius:1rem;background:#f3f3fb;margin:0.3rem;}
      .metric h2{margin:0;font-size:2.2rem;color:#3b82f6;}
      .metric p {margin:0;font-size:0.9rem;color:#666;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>🧠 Universal Metadata Extractor</h1>'
    '<p>LLM-powered classification &amp; extraction for any document.</p></div>',
    unsafe_allow_html=True
)

# ---------- 📊  live statistics ----------
feedback = load_feedback()

total_docs   = len({r["doc_id"] for r in feedback})
total_fields = sum(len(r.get("metadata_corrected", {})) for r in feedback)
today        = sum(
    1 for r in feedback
    if datetime.fromisoformat(r["timestamp"]).date() == datetime.utcnow().date()
)

cols = st.columns(3)
labels = ("Docs processed", "Fields corrected", "Docs today")
for col, value, label in zip(cols, (total_docs, total_fields, today), labels):
    col.markdown(
        f'<div class="metric"><h2>{value}</h2><p>{label}</p></div>',
        unsafe_allow_html=True
    )

st.markdown("---")
st.write(
    "Use the **sidebar ↖** to switch to *Inference* or *Training* pages."
)
