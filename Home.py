"""
Landing page – stylish hero header + live stats.
"""

from datetime import datetime, timezone
import streamlit as st
from utils.utils import load_feedback
from dotenv import load_dotenv
from utils.ui_components import inject_logo, inject_common_styles

# Load API key from .env
load_dotenv(override=True)

st.set_page_config("Extractly", page_icon="🪄", layout="wide")

# Inject logo and common styles
inject_logo("data/assets/data_reply.svg", height="80px")  # Adjust height as needed
inject_common_styles()

# Theme-adaptive CSS using Streamlit's CSS variables
if "home_css" not in st.session_state:
    st.markdown(
        """
    <style>
    .hero {
        text-align: center;
        margin: 3rem 0;
    }
    .hero h1 {
        font-size: 3.5rem;
        font-weight: 700;
        color: var(--text-color);
    }
    .hero p {
        font-size: 1.2rem;
        color: var(--text-color);
        opacity: 0.7;
    }
    .metric {
        padding: 1.5rem;
        border-radius: 1rem;
        background-color: var(--secondary-background-color);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        margin: 0.5rem;
        text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.1);
    }
    .metric h2 {
        margin: 0;
        font-size: 3rem;
        font-weight: 600;
        color: var(--primary-color);
    }
    .metric p {
        margin-top: 0.5rem;
        font-size: 1rem;
        color: var(--text-color);
    }
    .metric:hover {
        box-shadow: 0 0 16px rgba(var(--primary-color-rgb), 0.3);
        transition: 0.3s;
    }
    .sidebar-tip {
        text-align: center;
        color: var(--text-color);
        opacity: 0.6;
        margin-top: 2rem;
        font-size: 1rem;
    }
    /* Custom success rate colors that work in both themes */
    .success-high { color: #10b981 !important; }
    .success-medium { color: #f59e0b !important; }
    .success-low { color: #ef4444 !important; }
    </style>
    """,
        unsafe_allow_html=True,
    )
    st.session_state.home_css = True

# Hero header
st.markdown(
    """
<div class="hero">
  <h1>🪄 Extractly</h1>
  <p>AI-powered metadata classification & extraction for every document.</p>
</div>
""",
    unsafe_allow_html=True,
)

# Live stats with enhanced confidence metrics
feedback = load_feedback()
today_utc = datetime.now(timezone.utc).date()

total_docs = len({r["doc_id"] for r in feedback})
total_fields_corrected = sum(len(r.get("fields_corrected", [])) for r in feedback)

docs_today = 0
high_confidence_docs = 0

for r in feedback:
    try:
        if datetime.fromisoformat(r["timestamp"]).date() == today_utc:
            docs_today += 1

        # Count high confidence extractions
        if r.get("metadata_extracted"):
            non_empty_fields = sum(
                bool(v and str(v).strip()) for v in r["metadata_extracted"].values()
            )
            total_fields = len(r["metadata_extracted"])
            if total_fields > 0 and (non_empty_fields / total_fields) >= 0.7:
                high_confidence_docs += 1
    except Exception:
        continue

# Calculate success rate percentage
success_rate = int((high_confidence_docs / total_docs) * 100) if total_docs > 0 else 0

# Metric cards
cols = st.columns(4)
values = [
    ("Docs Today", docs_today, None),
    ("Total Docs", total_docs, None),
    ("Success Rate", f"{success_rate}%", success_rate),
    ("Fields Corrected", total_fields_corrected, None),
]

for col, (label, val, rate) in zip(cols, values):
    # Color coding for success rate
    color_style = ""
    if label == "Success Rate":
        if success_rate >= 80:
            color_style = "color: #10b981;"  # green
        elif success_rate >= 60:
            color_style = "color: #f59e0b;"  # yellow
        else:
            color_style = "color: #ef4444;"  # red

    col.markdown(
        f"""
    <div class="metric">
      <h2 style="{color_style}">{val}</h2>
      <p>{label}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("---")

st.markdown(
    '<div class="sidebar-tip">⬅ Use the sidebar to open <strong>Inference</strong> or <strong>Schemas</strong>.</div>',
    unsafe_allow_html=True,
)
