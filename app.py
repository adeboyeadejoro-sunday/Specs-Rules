from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Tuple

import streamlit as st


def update_spec_id_in_payload(payload: Dict[str, Any], new_spec_id: int) -> Tuple[int, int, Dict[str, Any]]:
    """
    Replace data.spec_id in every rules[*].data object.

    Parameters
    ----------
    payload : Dict[str, Any]
        Parsed JSON with top-level key 'rules' -> list.
    new_spec_id : int
        The new spec id to set on each rule's data.

    Returns
    -------
    updated_count : int
        Number of rules whose data was visited and had spec_id set.
    total_rules : int
        Total number of items in payload['rules'] list (if present).
    payload : Dict[str, Any]
        The modified payload (returned for convenience).
    """
    rules: List[Any] = payload.get("rules", [])
    updated = 0
    for item in rules:
        if isinstance(item, dict):
            d = item.get("data")
            if isinstance(d, dict):
                d["spec_id"] = int(new_spec_id)
                updated += 1
    return updated, len(rules), payload


st.set_page_config(page_title="Rules spec_id updater", page_icon="🧰", layout="centered")

st.title("Rules `spec_id` Updater 🧰")
st.caption("Upload a Rules JSON → set a new `spec_id` for all rules → download the updated file.")

with st.expander("Instructions", expanded=False):
    st.write(
        """
        1) Upload a `Rules_YYYYMMDD.json` with a top-level `"rules"` list.\n
        2) Enter the **new** integer `spec_id`.\n
        3) Click **Update** to preview counts.\n
        4) Click **Download** to save the new JSON.
        """
    )

uploaded = st.file_uploader("Upload Rules JSON", type=["json"])
new_spec_id: int = st.number_input("New spec_id (integer)", min_value=0, step=1, value=0)

if "updated_payload" not in st.session_state:
    st.session_state.updated_payload = None
    st.session_state.updated_count = 0
    st.session_state.total_rules = 0
    st.session_state.filename = "Rules_updated.json"

col1, col2 = st.columns(2)

with col1:
    run_btn = st.button("Update", type="primary")

with col2:
    clear_btn = st.button("Clear")

if clear_btn:
    st.session_state.updated_payload = None
    st.session_state.updated_count = 0
    st.session_state.total_rules = 0
    st.session_state.filename = "Rules_updated.json"
    st.experimental_rerun()

if run_btn:
    if not uploaded:
        st.error("Please upload a Rules JSON first.")
    else:
        try:
            # Read JSON
            content = uploaded.read().decode("utf-8")
            payload: Dict[str, Any] = json.loads(content)
            if "rules" not in payload or not isinstance(payload["rules"], list):
                st.error("Invalid JSON: missing top-level 'rules' list.")
            else:
                updated_count, total_rules, new_payload = update_spec_id_in_payload(payload, int(new_spec_id))
                st.session_state.updated_payload = new_payload
                st.session_state.updated_count = updated_count
                st.session_state.total_rules = total_rules
                # Suggest a filename like Rules_20251105_spec789.json if the original looks like Rules_*.json
                base_name = uploaded.name.rsplit(".", 1)[0]
                st.session_state.filename = f"{base_name}_spec{int(new_spec_id)}.json"
                st.success("Update complete.")
        except Exception as e:
            st.exception(e)

if st.session_state.updated_payload is not None:
    st.subheader("Summary")
    st.write(
        f"- Total rules found: **{st.session_state.total_rules}**\n"
        f"- Rules updated with new `spec_id`: **{st.session_state.updated_count}**\n"
        f"- Output filename: **{st.session_state.filename}**"
    )

    # Prepare bytes for download
    buffer = io.BytesIO()
    buffer.write(json.dumps(st.session_state.updated_payload, ensure_ascii=False, indent=2).encode("utf-8"))
    buffer.seek(0)

    st.download_button(
        label="Download updated JSON",
        data=buffer,
        file_name=st.session_state.filename,
        mime="application/json",
        use_container_width=True,
    )
