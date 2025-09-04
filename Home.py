"""
Landing page – stylish hero header + live stats.
"""

from datetime import datetime, timezone
import streamlit as st
from utils.utils import load_feedback
from dotenv import load_dotenv
from utils.ui_components import inject_logo, inject_common_styles

# Load API key from .env
load_dotenv(override=True)  # override any existing env vars

# ── colours
DARK_CARD_BG = "#0f172a"  # darker slate
ACCENT_COLOR = "#06b6d4"  # cyan-500
TEXT_COLOR = "#e2e8f0"  # soft white

st.set_page_config("Extractly", page_icon="🪄", layout="wide")

# Inject logo and common styles
inject_logo("data/assets/data_reply.svg", height="80px")  # Adjust height as needed
inject_common_styles()

# ── one-time CSS injection (avoid duplicates on rerun)
if "home_css" not in st.session_state:
    st.markdown(
        f"""
        <style>
          .hero {{text-align:center;margin:3rem 0;}}
          .hero h1 {{font-size:3.5rem;font-weight:700;color:{TEXT_COLOR};}}
          .hero p  {{font-size:1.2rem;color:#94a3b8;}}

          .metric {{
            padding:1.5rem;border-radius:1rem;
            background:{DARK_CARD_BG};box-shadow:0 8px 16px #0003;
            margin:0.5rem;text-align:center;
          }}
          .metric h2 {{margin:0;font-size:3rem;font-weight:600;color:{ACCENT_COLOR};}}
          .metric p  {{margin-top:0.5rem;font-size:1rem;color:{TEXT_COLOR};}}
          .metric:hover {{box-shadow:0 0 16px {ACCENT_COLOR}55;transition:0.3s;}}
          .sidebar-tip {{text-align:center;color:#64748b;margin-top:2rem;font-size:1rem;}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state.home_css = True

# ── hero header
st.markdown(
    """
    <div class="hero">
      <h1>🪄 Extractly</h1>
      <p>AI-powered metadata classification &amp; extraction for every document.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── live stats
feedback = load_feedback()
today_utc = datetime.now(timezone.utc).date()

total_docs = len({r["doc_id"] for r in feedback})
total_fields_corrected = sum(len(r.get("fields_corrected", [])) for r in feedback)

docs_today = 0
for r in feedback:
    try:
        if datetime.fromisoformat(r["timestamp"]).date() == today_utc:
            docs_today += 1
    except Exception:
        continue  # ignore bad or missing timestamps

# ── metric cards
cols = st.columns(3)
values = [
    ("Docs Reviewed Today", docs_today),
    ("Total Reviewed Docs", total_docs),
    ("Total Fields Corrected", total_fields_corrected),
]

for col, (label, val) in zip(cols, values):
    col.markdown(
        f"""
        <div class="metric">
          <h2>{val:,}</h2>
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
