# utils/ui_components.py

import streamlit as st
import base64


def inject_logo(svg_path="data/assets/data_reply.svg", height="80px"):
    """
    Inject logo above navigation using CSS - runs every time.

    Parameters:
    -----------
    svg_path : str
        Path to the SVG logo file
    height : str
        CSS height value for the logo area (e.g., "80px", "100px")
    """

    def get_base64_of_svg(svg_path):
        """Convert SVG to base64 string"""
        try:
            with open(svg_path, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except FileNotFoundError:
            st.warning(f"Logo file not found: {svg_path}")
            return None

    # Get the SVG as base64
    svg_base64 = get_base64_of_svg(svg_path)

    # ALWAYS inject the CSS (no session state check)
    if svg_base64:
        st.markdown(
            f"""
        <style>
        /* Logo injection above navigation */
        [data-testid="stSidebarNav"]::before {{
            content: "";
            display: block;
            width: 100%;
            height: {height};
            background-image: url("data:image/svg+xml;base64,{svg_base64}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: contain;
            margin-bottom: 1rem;
            padding: 1rem;
        }}
        
        /* Ensure proper spacing */
        [data-testid="stSidebarNav"] {{
            padding-top: 1rem;
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )


def inject_common_styles():
    """
    Inject common theme-adaptive styles for the app.
    Call this on pages that need the standard styling.
    """

    # Always inject the CSS (remove session state dependency)
    st.markdown(
        """
    <style>
    /* Hero section */
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
    
    /* Metric cards */
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
    
    /* Sidebar tip */
    .sidebar-tip {
        text-align: center;
        color: var(--text-color);
        opacity: 0.6;
        margin-top: 2rem;
        font-size: 1rem;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
