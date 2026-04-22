"""
Spec Name Updater - Streamlit App

Converts a cleanup-report JSON (with 'spec id' and 'Cleaned Name' fields)
into the LIMS-importable update payload format.
"""

import json
from io import BytesIO
import streamlit as st
import pandas as pd


# ---------- Core transformation ----------

def transform_records(records):
    """
    Convert input records into the LIMS update payload.

    Each input record must contain:
      - 'spec id'       -> becomes 'id' (coerced to string)
      - 'Cleaned Name'  -> becomes data.name (coerced to string, stripped)

    Returns: (payload_dict, skipped_list)
      payload_dict -> {"specs": [ {action, id, data: {name}}, ... ]}
      skipped_list -> list of (index, reason) for records that couldn't be processed
    """
    specs_out = []
    skipped = []

    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            skipped.append((i, "Not a JSON object"))
            continue

        spec_id = rec.get("spec id")
        cleaned = rec.get("Cleaned Name")

        if spec_id is None:
            skipped.append((i, "Missing 'spec id'"))
            continue
        if cleaned is None or (isinstance(cleaned, str) and not cleaned.strip()):
            skipped.append((i, "Missing or empty 'Cleaned Name'"))
            continue

        # Coerce both to string. Strip name defensively in case hidden chars slipped through.
        id_str = str(spec_id).strip()
        name_str = str(cleaned).strip()

        specs_out.append({
            "action": "update",
            "id": id_str,
            "data": {"name": name_str},
        })

    return {"specs": specs_out}, skipped


# ---------- UI ----------

st.set_page_config(page_title="Spec Name Updater", page_icon="🧹", layout="wide")

st.title("🧹 Spec Name Updater")
st.caption(
    "Upload a cleanup-report JSON (array of records with `spec id` and `Cleaned Name`) "
    "and download a LIMS-ready update payload."
)

with st.expander("Expected input format", expanded=False):
    st.code(
        json.dumps(
            [
                {
                    "Spec Name": "ICP_GUM-MGM-01 ",
                    "spec id": 1717,
                    "Hidden Char Count": 1,
                    "Cleaned Name": "ICP_GUM-MGM-01",
                    "Edit Link": "ICP_GUM-MGM-01 ",
                }
            ],
            indent=2,
        ),
        language="json",
    )

uploaded = st.file_uploader("Upload input JSON", type=["json"])

if uploaded is not None:
    # --- Parse ---
    try:
        raw = uploaded.read().decode("utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    if not isinstance(data, list):
        st.error("Top-level JSON must be an **array** of spec records.")
        st.stop()

    # --- Transform ---
    payload, skipped = transform_records(data)

    # --- Summary ---
    total = len(data)
    ok = len(payload["specs"])
    col1, col2, col3 = st.columns(3)
    col1.metric("Input records", total)
    col2.metric("Converted", ok)
    col3.metric("Skipped", len(skipped))

    if skipped:
        with st.expander(f"⚠️ {len(skipped)} skipped record(s)", expanded=True):
            skip_df = pd.DataFrame(skipped, columns=["Input index", "Reason"])
            st.dataframe(skip_df, hide_index=True, use_container_width=True)

    # --- Preview ---
    if ok:
        st.subheader("Preview")
        preview_df = pd.DataFrame(
            [
                {"id": s["id"], "new name": s["data"]["name"]}
                for s in payload["specs"]
            ]
        )
        st.dataframe(preview_df, hide_index=True, use_container_width=True)

        st.subheader("Output JSON")
        output_str = json.dumps(payload, indent=4, ensure_ascii=False)
        st.code(output_str, language="json")

        # --- Download ---
        out_bytes = BytesIO(output_str.encode("utf-8"))
        base_name = uploaded.name.rsplit(".", 1)[0]
        st.download_button(
            label="⬇️ Download spec_name_updater.json",
            data=out_bytes,
            file_name=f"{base_name}__updater.json",
            mime="application/json",
        )
    else:
        st.warning("No records could be converted. Check the skipped list above.")
else:
    st.info("Waiting for a JSON file…")
