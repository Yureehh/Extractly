"""
Landing page – stylish hero header + live stats.
"""



import streamlit as st
from datetime import datetime, timezone
from src.utils import load_feedback

# Colors
DARK_CARD_BG = "#0f172a"  # darker slate
ACCENT_COLOR = "#06b6d4"  # cyan-500 (turquoise)
TEXT_COLOR = "#e2e8f0"  # slate-200 (soft white)

st.set_page_config(page_title="Extractly", page_icon="🪄", layout="wide")

# Improved styling
st.markdown(
    f"""
    <style>
      .hero {{
        text-align:center;
        margin-top:3rem;
        margin-bottom:3rem;
      }}
      .hero h1 {{
        font-size:3.5rem;
        font-weight: 700;
        color: {TEXT_COLOR};
      }}
      .hero p {{
        font-size:1.2rem;
        color: #94a3b8;
      }}
      .metric {{
        padding:1.5rem;
        border-radius:1rem;
        background:{DARK_CARD_BG};
        box-shadow:0 8px 16px #00000033;
        margin:0.5rem;
        text-align:center;
      }}
      .metric h2 {{
        margin:0;
        font-size:3rem;
        font-weight:600;
        color:{ACCENT_COLOR};
      }}
      .metric p {{
        margin-top:0.5rem;
        font-size:1rem;
        color:{TEXT_COLOR};
      }}
      .metric:hover {{
        box-shadow:0 0 16px {ACCENT_COLOR}88;
        transition:0.3s ease-in-out;
      }}
      .sidebar-tip {{
        text-align:center;
        color:#64748b;
        margin-top:2rem;
        font-size:1rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Hero section
st.markdown(
    """
    <div class="hero">
      <h1>🪄 Extractly</h1>
      <p>AI-powered metadata classification & extraction for every document.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- 📊 live statistics ----------
feedback = load_feedback()

total_docs = len({r["doc_id"] for r in feedback})
total_fields = sum(len(r.get("metadata_corrected", {})) for r in feedback)
today = sum(
    datetime.fromisoformat(r["timestamp"]).date()
    == datetime.now(timezone.utc).date()
    for r in feedback
)

# Display metrics
cols = st.columns(3)
metrics = [
    ("Docs Today", today),
    ("Total Docs", total_docs),
    ("Fields Corrected", total_fields),
]

for col, (label, value) in zip(cols, metrics):
    col.markdown(
        f"""
        <div class="metric">
          <h2>{value}</h2>
          <p>{label}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown(
    '<div class="sidebar-tip">⬅️ Use the sidebar to navigate to <strong>Inference</strong> or <strong>Training</strong>.</div>',
    unsafe_allow_html=True,
)
