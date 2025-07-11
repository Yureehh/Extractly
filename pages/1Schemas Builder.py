# sourcery skip: swap-if-else-branches, use-named-expression
import pandas as pd
import streamlit as st
import json
from pathlib import Path
from src.schema_manager import SchemaManager

# ───────────────── constants / init ────────────────────────────────
# Get the project root directory (parent of the pages directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "schemas"
CUSTOM_JSON = DATA_DIR / "custom_schemas.json"
DATA_DIR.mkdir(exist_ok=True)

SM = SchemaManager()  # load built-ins
custom_data = {}
if CUSTOM_JSON.exists():  # preload customs
    custom_data = json.loads(CUSTOM_JSON.read_text())
    SM.add_custom(custom_data)

# ───────────────── session defaults ────────────────────────────────
st.session_state.setdefault("editing_doc", None)
st.session_state.setdefault("field_data", [{"name": "", "description": ""}])
st.session_state.setdefault("rename_open", False)
st.session_state.setdefault("reset_now", False)

# ───────────────── handle one-shot reset flag BEFORE widgets ───────
if st.session_state.reset_now:
    st.session_state.pop("doc_name_input", None)  # clear text box value
    st.session_state.editing_doc = None
    st.session_state.field_data = [{"name": "", "description": ""}]
    st.session_state.reset_now = False  # consume flag

# ───────────────── page meta ───────────────────────────────────────
st.set_page_config("Schema Builder", "🧬", layout="wide")
st.title("🧬 Schema Builder")

# ───────────────── sidebar: schema list & actions ──────────────────
with st.sidebar:
    st.subheader("📦 Schemas")

    for dt in SM.get_types():
        col_name, col_del = st.columns([3, 1])
        with col_name:
            if st.button(dt, key=f"sel_{dt}"):
                st.session_state.field_data = SM.get(dt) or [
                    {"name": "", "description": ""}
                ]
                st.session_state.editing_doc = dt
                st.session_state.rename_open = False
                st.rerun()

        with col_del:
            if st.button("🗑️", key=f"del_{dt}", help="Delete"):
                SM.delete(dt)
                custom_data.pop(dt, None)
                CUSTOM_JSON.write_text(
                    json.dumps(custom_data, indent=2, ensure_ascii=False)
                )
                if st.session_state.editing_doc == dt:
                    st.session_state.editing_doc = None
                    st.session_state.rename_open = False
                    st.session_state.field_data = [{"name": "", "description": ""}]
                st.rerun()

    # ── Rename + Clear all  (same row) ───────────────────────────────
    col_ren, col_clear = st.columns(2)

    # ── Rename current ────────────────────────────────────────────
    with col_ren:
        if st.button("✏️ Rename current", disabled=not st.session_state.editing_doc):
            st.session_state.rename_open = not st.session_state.rename_open

        if st.session_state.rename_open and st.session_state.editing_doc:
            with st.expander("Rename schema", expanded=True):
                new_name = st.text_input(
                    "New doc-type name",
                    value=st.session_state.editing_doc,
                    key="rename_input",
                )

                # ✅ sidebar-safe: no st.columns(), just stacked buttons
                if st.button("✔️ Confirm rename"):
                    old = st.session_state.editing_doc
                    SM.rename(old, new_name)
                    custom_data[new_name] = custom_data.pop(old)
                    CUSTOM_JSON.write_text(
                        json.dumps(custom_data, indent=2, ensure_ascii=False)
                    )
                    st.session_state.editing_doc = new_name
                    st.session_state.field_data = SM.get(new_name)
                    st.session_state.rename_open = False
                    st.rerun()

                if st.button("✖️ Cancel"):
                    st.session_state.rename_open = False

    # ── Clear all ────────────────────────────────────────────────
    with col_clear:
        if st.button("🚮 Clear all CUSTOM schemas"):
            custom_data.clear()
            CUSTOM_JSON.unlink(missing_ok=True)
            st.session_state.editing_doc = None
            st.session_state.rename_open = False
            st.session_state.field_data = [{"name": "", "description": ""}]
            st.rerun()

    # ── JSON import ───────────────────────────────────────────────
    st.subheader("⇡ Import JSON schema file")
    up = st.file_uploader(
        label=" ",
        type=["json"],
        label_visibility="collapsed",
    )
    if up:
        try:
            data = json.load(up)
            SM.add_custom(data)
            custom_data.update(data)
            CUSTOM_JSON.write_text(
                json.dumps(custom_data, indent=2, ensure_ascii=False)
            )
            st.success(f"Imported {len(data)} doc-types.")
            st.rerun()
        except Exception as e:
            st.error(f"Bad JSON: {e}")

# ───────────────── MAIN AREA ───────────────────────────────────────
doc_name = st.text_input(
    "Document type name (create new or edit existing)",
    value=st.session_state.editing_doc or "",
    key="doc_name_input",
)

if not doc_name:
    st.info("Enter a document type name to begin.")
    st.stop()

# ── keep or clear table based on doc_name validity ────────────────
if doc_name != st.session_state.editing_doc:
    if doc_name in SM.get_types():  # switch to known schema
        st.session_state.editing_doc = doc_name
        st.session_state.field_data = SM.get(doc_name) or [
            {"name": "", "description": ""}
        ]
    else:  # unknown name → blank table
        st.session_state.editing_doc = None
        st.session_state.field_data = [{"name": "", "description": ""}]

st.subheader(f"Fields for **{doc_name}**")

schema_desc = st.text_area(
    "High-level description",
    value=SM.get_description(doc_name),
    placeholder="e.g. Italian electronic invoice issued by suppliers…",
)

raw_table = st.data_editor(
    st.session_state.field_data,  # static snapshot
    num_rows="dynamic",
    use_container_width=True,
    key="field_editor",
)

# normalise ↓
table_rows = (
    raw_table.fillna("").to_dict(orient="records")
    if isinstance(raw_table, pd.DataFrame)
    else raw_table
)
table_rows = [
    {
        "name": r.get("name", " ").strip(),
        "description": r.get("description", r.get("description ", " ")).strip(),
    }
    for r in table_rows
]


# ───────────────── save / reset buttons ───────────────────────────
col_save, col_reset = st.columns(2)

with col_save:
    if st.button("💾 Save schema"):
        clean = [row for row in table_rows if row["name"]]
        if not clean:
            st.error("Must have at least one field.")
        else:
            payload = {"description": schema_desc.strip(), "fields": clean}
            SM.add_custom({doc_name: payload})
            custom_data[doc_name] = payload  # ← store whole dict
            CUSTOM_JSON.write_text(
                json.dumps(custom_data, indent=2, ensure_ascii=False)
            )
            st.success(f"Saved {len(clean)} fields for “{doc_name}”.")
            st.session_state.field_data = clean
            st.session_state.editing_doc = doc_name

with col_reset:
    if st.button("↺ Reset"):
        st.session_state.reset_now = True
        st.rerun()
