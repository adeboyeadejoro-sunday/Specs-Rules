"""
Streamlit app: transform a LIMS specification JSON export into the
samples_spec_updater format.

Input shape (array of records):
    [
        {
            "Sample": "...",
            "id": <int>,
            "SKU / LOT / Description": "...",
            "Packages Ordered": "...",
            "date": "...",
            "spec_id1": <int>,
            "spec_id2": <int|null>
        },
        ...
    ]

Output shape:
    {
        "samples": [
            {
                "action": "update",
                "id": "<str>",
                "data": {
                    "spec_id1": "<str>",
                    "spec_id2": "<str>" | null
                }
            },
            ...
        ]
    }
"""

import json
from datetime import datetime
from io import BytesIO

import streamlit as st


REQUIRED_FIELDS = ("id", "spec_id1", "spec_id2")
PREVIEW_COUNT = 5


def transform_records(records):
    """
    Transform a list of input records into the updater payload.

    Raises ValueError with a descriptive message if validation fails.
    The caller is expected to display the error to the user.
    """
    if not isinstance(records, list):
        raise ValueError(
            "Expected the root of the JSON file to be an array of sample "
            f"records, but got {type(records).__name__}."
        )

    if len(records) == 0:
        raise ValueError("The uploaded JSON array is empty — nothing to transform.")

    transformed = []

    for index, record in enumerate(records):
        # Identify the record in error messages using its Sample name if present,
        # otherwise fall back to the array index.
        sample_name = (
            record.get("Sample")
            if isinstance(record, dict) and record.get("Sample")
            else f"<index {index}>"
        )

        if not isinstance(record, dict):
            raise ValueError(
                f"Record at index {index} is not a JSON object "
                f"(got {type(record).__name__})."
            )

        # Fail loudly if any required field is missing. `spec_id2` is allowed
        # to be null, but the key itself must exist.
        for field in REQUIRED_FIELDS:
            if field not in record:
                raise ValueError(
                    f"Record '{sample_name}' (index {index}) is missing "
                    f"required field '{field}'."
                )

        id_value = record["id"]
        spec_id1_value = record["spec_id1"]
        spec_id2_value = record["spec_id2"]

        # `id` and `spec_id1` must be present and non-null.
        if id_value is None:
            raise ValueError(
                f"Record '{sample_name}' (index {index}) has a null 'id'."
            )
        if spec_id1_value is None:
            raise ValueError(
                f"Record '{sample_name}' (index {index}) has a null 'spec_id1'."
            )

        transformed.append(
            {
                "action": "update",
                "id": str(id_value),
                "data": {
                    "spec_id1": str(spec_id1_value),
                    # Preserve null for spec_id2; otherwise stringify.
                    "spec_id2": None if spec_id2_value is None else str(spec_id2_value),
                },
            }
        )

    return {"samples": transformed}


def build_filename(now=None):
    """Build a timestamped output filename: samples_spec_updater_YYYYMMDD_HHMM.json"""
    now = now or datetime.now()
    return f"samples_spec_updater_{now.strftime('%Y%m%d_%H%M')}.json"


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Spec Updater", page_icon="🧪")

st.title("🧪 Samples Spec Updater")
st.write(
    "Upload a LIMS specification JSON export. This app will transform it into "
    "the `samples_spec_updater` format, ready to download."
)

uploaded = st.file_uploader("Upload input JSON", type=["json"])

if uploaded is not None:
    # Parse JSON ---------------------------------------------------------
    try:
        raw_bytes = uploaded.read()
        records = json.loads(raw_bytes)
    except json.JSONDecodeError as e:
        st.error(f"❌ Could not parse the uploaded file as JSON: {e}")
        st.stop()

    # Transform ----------------------------------------------------------
    try:
        payload = transform_records(records)
    except ValueError as e:
        st.error(f"❌ Validation failed: {e}")
        st.stop()

    total = len(payload["samples"])
    st.success(f"✅ Transformed {total} record{'s' if total != 1 else ''}.")

    # Preview ------------------------------------------------------------
    st.subheader("Preview")

    preview_samples = payload["samples"][:PREVIEW_COUNT]
    preview_payload = {"samples": preview_samples}
    preview_text = json.dumps(preview_payload, indent=4, ensure_ascii=False)

    if total > PREVIEW_COUNT:
        st.caption(f"Showing {PREVIEW_COUNT} of {total} records.")
    else:
        st.caption(f"Showing all {total} record{'s' if total != 1 else ''}.")

    st.code(preview_text, language="json")

    # Download -----------------------------------------------------------
    full_text = json.dumps(payload, indent=4, ensure_ascii=False)
    filename = build_filename()

    st.download_button(
        label=f"⬇️ Download {filename}",
        data=full_text.encode("utf-8"),
        file_name=filename,
        mime="application/json",
    )
