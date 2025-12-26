from __future__ import annotations

import base64
from pathlib import Path
import streamlit as st


def inject_branding(logo_path: str | Path, height: str = "64px") -> None:
    logo_path = Path(logo_path)
    if not logo_path.exists():
        return

    encoded = base64.b64encode(logo_path.read_bytes()).decode()
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebarNav"]::before {{
            content: "";
            display: block;
            width: 100%;
            height: {height};
            background-image: url("data:image/svg+xml;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: contain;
            margin-bottom: 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --extractly-border: rgba(148, 163, 184, 0.35);
            --extractly-card: rgba(15, 23, 42, 0.04);
        }
        .extractly-hero {
            padding: 3rem 2rem;
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(59,130,246,0.10), rgba(236,254,255,0.5));
            border: 1px solid var(--extractly-border);
        }
        .extractly-hero h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
        }
        .extractly-card {
            padding: 1.5rem;
            border-radius: 16px;
            border: 1px solid var(--extractly-border);
            background: var(--extractly-card);
        }
        .extractly-step {
            padding: 1rem 1.25rem;
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.03);
            border: 1px dashed var(--extractly-border);
        }
        .extractly-section-title {
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"<div class='extractly-section-title'><strong>{title}</strong></div>", unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)
