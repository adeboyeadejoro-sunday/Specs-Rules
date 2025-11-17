from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import streamlit as st


JsonDict = Dict[str, Any]


# =========================
# Shared JSON / rules utils
# =========================

def ensure_rules_payload(payload: JsonDict) -> List[Any]:
    """
    Ensure payload has a top-level 'rules' list and return it.

    Raises
    ------
    ValueError
        If the structure is invalid.
    """
    rules: Any = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Invalid JSON: missing top-level 'rules' list.")
    return rules


def read_uploaded_json(uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile") -> JsonDict:
    """
    Read and parse an uploaded JSON file from Streamlit.
    """
    content: str = uploaded_file.read().decode("utf-8")
    payload: JsonDict = json.loads(content)
    ensure_rules_payload(payload)
    return payload


def make_download_buffer(payload: JsonDict) -> io.BytesIO:
    """
    Serialize payload to BytesIO for Streamlit download_button.
    """
    buffer = io.BytesIO()
    buffer.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    buffer.seek(0)
    return buffer


def sanitize_filename_base(name: str) -> str:
    """
    Strip extension from uploaded filename to use as base.
    """
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name


# =========================
# 1) Update spec_id
# =========================

def update_spec_id_in_payload(payload: JsonDict, new_spec_id: int) -> Tuple[int, int, JsonDict]:
    """
    Replace data.spec_id in every rules[*].data object.

    Returns
    -------
    updated_count : int
        Number of rules that had spec_id set.
    total_rules : int
        Total number of items in payload['rules'].
    payload : Dict[str, Any]
        The modified payload.
    """
    rules: List[Any] = payload.get("rules", [])
    updated: int = 0
    for item in rules:
        if isinstance(item, dict):
            data = item.get("data")
            if isinstance(data, dict):
                data["spec_id"] = int(new_spec_id)
                updated += 1
    return updated, len(rules), payload


# =========================
# 2) Update DDF_unit
# =========================

def parse_param_ids(values: Optional[Iterable[str]]) -> Optional[Set[int]]:
    """
    Parse a comma- or whitespace-separated iterable of param IDs into a set of ints.
    Empty input -> None.
    """
    if not values:
        return None
    out: Set[int] = set()
    for v in values:
        v_stripped: str = v.strip()
        if not v_stripped:
            continue
        for part in v_stripped.replace(",", " ").split():
            part = part.strip()
            if part:
                out.add(int(part))
    return out if out else None


def param_id_matches(item: Dict[str, Any], restrict_ids: Optional[Set[int]]) -> bool:
    """
    Return True if this rule item should be affected according to restrict_ids.
    If restrict_ids is None, everything matches.
    """
    if restrict_ids is None:
        return True

    data = item.get("data")
    if not isinstance(data, dict):
        return False

    pid = data.get("parametertype_id")
    try:
        return int(pid) in restrict_ids
    except Exception:
        return False


def update_DDF_unit(
    payload: JsonDict,
    new_unit: Optional[str],
    *,
    only_missing: bool = False,
    restrict_param_ids: Optional[Set[int]] = None,
) -> Tuple[int, int, JsonDict]:
    """
    Update data.DDF_unit in each rule, with optional filters.

    Parameters
    ----------
    payload : Dict[str, Any]
        Parsed JSON with top-level 'rules' list.
    new_unit : Optional[str]
        String to set as unit, or None to set JSON null.
    only_missing : bool
        If True, only update rules where DDF_unit is currently None / empty / 'null'.
    restrict_param_ids : Optional[Set[int]]
        If provided, only update rules whose data.parametertype_id is in this set.
    """
    rules: List[Any] = payload.get("rules", [])
    updated: int = 0

    for item in rules:
        if not isinstance(item, dict):
            continue
        if not param_id_matches(item, restrict_param_ids):
            continue

        data = item.get("data")
        if not isinstance(data, dict):
            continue

        current = data.get("DDF_unit")
        if only_missing:
            # Treat None, "", and "null" (case-insensitive) as missing
            missing: bool = (current is None) or (
                isinstance(current, str) and current.strip().lower() in ("", "null")
            )
            if not missing:
                continue

        data["DDF_unit"] = new_unit  # can be None -> JSON null
        updated += 1

    return updated, len(rules), payload


# =========================
# 3) Update ANY key (dot-path)
# =========================

def _split_path(path: str) -> List[str]:
    if not path or path.strip() == "":
        raise ValueError("Key path must be non-empty, e.g. 'action' or 'data.spec_id'.")
    return [p for p in path.split(".") if p]


def get_by_path(obj: Any, path: Sequence[str]) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def set_by_path(obj: Dict[str, Any], path: Sequence[str], value: Any) -> None:
    cur: Dict[str, Any] = obj
    for key in path[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]  # type: ignore[assignment]
    cur[path[-1]] = value


def parse_value(raw: str, as_type: str) -> Any:
    """
    Parse a string value according to the requested type.

    as_type:
        - 'auto'
        - 'str'
        - 'int'
        - 'float'
        - 'bool'
        - 'null'
        - 'json'
    """
    t: str = as_type.lower()

    if t == "str":
        return raw
    if t == "int":
        return int(raw)
    if t == "float":
        return float(raw)
    if t == "bool":
        low = raw.strip().lower()
        if low in ("true", "1", "yes", "y", "on"):
            return True
        if low in ("false", "0", "no", "n", "off"):
            return False
        raise ValueError(f"Cannot parse boolean from {raw!r}")
    if t == "null":
        return None
    if t == "json":
        # interpret as JSON literal (object/array/number/bool/null/string)
        return json.loads(raw)

    # auto mode
    low = raw.strip().lower()
    if low in ("null", ""):
        return None
    if low in ("true", "false"):
        return low == "true"

    # int?
    try:
        if raw.strip().startswith(("+", "-")):
            int(raw)
            return int(raw)
        if raw.isdigit():
            return int(raw)
    except Exception:
        pass

    # float?
    try:
        return float(raw)
    except Exception:
        pass

    # fallback string
    return raw


def update_key_for_rules(
    payload: JsonDict,
    key_path: str,
    new_value: Any,
    *,
    only_missing: bool = False,
    restrict_param_ids: Optional[Set[int]] = None,
) -> Tuple[int, int, JsonDict]:
    """
    Update a key (by dot-path) in every item of payload['rules'].

    Returns
    -------
    updated_count, total_rules, payload
    """
    rules: List[Any] = payload.get("rules")  # type: ignore[assignment]
    if not isinstance(rules, list):
        raise ValueError("Input JSON must have top-level 'rules' list.")

    path: List[str] = _split_path(key_path)
    updated: int = 0

    for item in rules:
        if not isinstance(item, dict):
            continue
        if not param_id_matches(item, restrict_param_ids):
            continue

        if only_missing:
            current = get_by_path(item, path)
            missing: bool = (current is None) or (
                isinstance(current, str) and current.strip().lower() in ("", "null")
            )
            if not missing:
                continue

        set_by_path(item, path, new_value)
        updated += 1

    return updated, len(rules), payload


# =========================
# 4) Remove parameters by parametertype_id
# =========================

def remove_params_from_payload(
    payload: JsonDict,
    param_ids: List[int],
) -> Tuple[int, int, JsonDict]:
    """
    Remove all rules where data.parametertype_id is in param_ids.

    Returns
    -------
    removed_count, total_rules, payload
    """
    rules: List[Any] = payload.get("rules", [])
    total: int = len(rules)
    keep: List[Any] = []
    removed_count: int = 0
    target_ids: Set[int] = set(param_ids)

    for rule in rules:
        pid_int: Optional[int] = None
        if isinstance(rule, dict):
            data = rule.get("data")
            if isinstance(data, dict):
                pid = data.get("parametertype_id")
                try:
                    pid_int = int(pid)
                except Exception:
                    pid_int = None

        if pid_int is not None and pid_int in target_ids:
            removed_count += 1
            continue
        keep.append(rule)

    payload["rules"] = keep
    return removed_count, total, payload


# =========================
# 5) Range calculator (no JSON)
# =========================

@dataclass(frozen=True)
class ActiveBands:
    low_ok: float
    low_perfect: float
    high_perfect: float
    high_ok2: float


def fmt(value: float) -> str:
    return f"{value:.2f}"


def compute_active_bands(target: float) -> ActiveBands:
    """
    Fixed percentage bands for type='active'.

    - low_ok       = 0.80 * target
    - low_perfect  = 0.90 * target
    - high_perfect = 1.25 * target
    - high_ok2     = 1.50 * target
    """
    return ActiveBands(
        low_ok=0.80 * target,
        low_perfect=0.90 * target,
        high_perfect=1.25 * target,
        high_ok2=1.50 * target,
    )


# =========================
# Streamlit pages / workflows
# =========================

def render_update_spec_id_tool() -> None:
    st.subheader("Update `spec_id` in Rules JSON")

    uploaded = st.file_uploader("Upload Rules JSON", type=["json"], key="spec_uploader")
    new_spec_id: int = st.number_input("New spec_id (integer)", min_value=0, step=1, value=0)

    if "spec_updated_payload" not in st.session_state:
        st.session_state.spec_updated_payload = None
        st.session_state.spec_updated_count = 0
        st.session_state.spec_total_rules = 0
        st.session_state.spec_filename = "Rules_updated_spec.json"

    col1, col2 = st.columns(2)
    with col1:
        run_btn = st.button("Update spec_id", type="primary", use_container_width=True)
    with col2:
        clear_btn = st.button("Clear spec_id result", use_container_width=True)

    if clear_btn:
        st.session_state.spec_updated_payload = None
        st.session_state.spec_updated_count = 0
        st.session_state.spec_total_rules = 0
        st.session_state.spec_filename = "Rules_updated_spec.json"
        st.experimental_rerun()

    if run_btn:
        if not uploaded:
            st.error("Please upload a Rules JSON first.")
        else:
            try:
                payload = read_uploaded_json(uploaded)
                updated_count, total_rules, new_payload = update_spec_id_in_payload(payload, int(new_spec_id))
                st.session_state.spec_updated_payload = new_payload
                st.session_state.spec_updated_count = updated_count
                st.session_state.spec_total_rules = total_rules

                base_name = sanitize_filename_base(uploaded.name)
                st.session_state.spec_filename = f"{base_name}_spec{int(new_spec_id)}.json"
                st.success("spec_id update complete.")
            except Exception as e:
                st.exception(e)

    if st.session_state.spec_updated_payload is not None:
        st.markdown("### Summary")
        st.write(
            f"- Total rules found: **{st.session_state.spec_total_rules}**\n"
            f"- Rules updated with new `spec_id`: **{st.session_state.spec_updated_count}**\n"
            f"- Output filename: **{st.session_state.spec_filename}**"
        )

        buffer = make_download_buffer(st.session_state.spec_updated_payload)
        st.download_button(
            label="Download updated JSON",
            data=buffer,
            file_name=st.session_state.spec_filename,
            mime="application/json",
            use_container_width=True,
        )


def render_update_unit_tool() -> None:
    st.subheader("Update `DDF_unit` in Rules JSON")

    uploaded = st.file_uploader("Upload Rules JSON", type=["json"], key="unit_uploader")

    col1, col2 = st.columns([2, 1])
    with col1:
        new_unit_str: str = st.text_input(
            "New DDF_unit (leave blank to set JSON null)",
            value="",
            placeholder="e.g. mg/kg",
        )
    with col2:
        only_missing: bool = st.checkbox("Only if missing / null", value=False)

    restrict_raw: str = st.text_input(
        "Restrict to parametertype_id(s) (optional)",
        value="",
        help="Comma- or space-separated list, e.g. 5239, 6001, 7002. Leave empty to update all.",
    )

    if "unit_updated_payload" not in st.session_state:
        st.session_state.unit_updated_payload = None
        st.session_state.unit_updated_count = 0
        st.session_state.unit_total_rules = 0
        st.session_state.unit_filename = "Rules_updated_unit.json"

    col_run, col_clear = st.columns(2)
    with col_run:
        run_btn = st.button("Update DDF_unit", type="primary", use_container_width=True)
    with col_clear:
        clear_btn = st.button("Clear unit result", use_container_width=True)

    if clear_btn:
        st.session_state.unit_updated_payload = None
        st.session_state.unit_updated_count = 0
        st.session_state.unit_total_rules = 0
        st.session_state.unit_filename = "Rules_updated_unit.json"
        st.experimental_rerun()

    if run_btn:
        if not uploaded:
            st.error("Please upload a Rules JSON first.")
        else:
            try:
                payload = read_uploaded_json(uploaded)
                restrict_ids = parse_param_ids([restrict_raw]) if restrict_raw.strip() else None
                new_unit: Optional[str] = new_unit_str if new_unit_str.strip() != "" else None

                updated_count, total_rules, new_payload = update_DDF_unit(
                    payload,
                    new_unit=new_unit,
                    only_missing=only_missing,
                    restrict_param_ids=restrict_ids,
                )

                st.session_state.unit_updated_payload = new_payload
                st.session_state.unit_updated_count = updated_count
                st.session_state.unit_total_rules = total_rules

                base_name = sanitize_filename_base(uploaded.name)
                unit_label = "null" if new_unit is None else new_unit.replace("/", "").replace(" ", "")
                st.session_state.unit_filename = f"{base_name}_unit_{unit_label}.json"

                st.success("DDF_unit update complete.")
            except Exception as e:
                st.exception(e)

    if st.session_state.unit_updated_payload is not None:
        st.markdown("### Summary")
        st.write(
            f"- Total rules found: **{st.session_state.unit_total_rules}**\n"
            f"- Rules updated with new `DDF_unit`: **{st.session_state.unit_updated_count}**\n"
            f"- Output filename: **{st.session_state.unit_filename}**"
        )

        buffer = make_download_buffer(st.session_state.unit_updated_payload)
        st.download_button(
            label="Download updated JSON",
            data=buffer,
            file_name=st.session_state.unit_filename,
            mime="application/json",
            use_container_width=True,
        )


def render_update_any_key_tool() -> None:
    st.subheader("Update any key (dot-path) in Rules JSON")

    uploaded = st.file_uploader("Upload Rules JSON", type=["json"], key="any_uploader")

    key_path: str = st.text_input(
        "Key path (dot notation)",
        value="data.action",
        help="Examples: 'action', 'data.spec_id', 'data.DDF_unit'",
    )

    col_val, col_type = st.columns([2, 1])
    with col_val:
        raw_value: str = st.text_input(
            "New value (as text)",
            value="update",
            help="Interpretation is controlled by 'Value type' below.",
        )
    with col_type:
        value_type: str = st.selectbox(
            "Value type",
            options=["auto", "str", "int", "float", "bool", "null", "json"],
            index=0,
        )

    only_missing: bool = st.checkbox(
        "Only update if current value is missing / empty / 'null'",
        value=False,
    )

    restrict_raw: str = st.text_input(
        "Restrict to parametertype_id(s) (optional)",
        value="",
        help="Comma- or space-separated list, e.g. 5239, 6001, 7002. Leave empty to update all.",
    )

    if "any_updated_payload" not in st.session_state:
        st.session_state.any_updated_payload = None
        st.session_state.any_updated_count = 0
        st.session_state.any_total_rules = 0
        st.session_state.any_filename = "Rules_updated_key.json"

    col_run, col_clear = st.columns(2)
    with col_run:
        run_btn = st.button("Update key", type="primary", use_container_width=True)
    with col_clear:
        clear_btn = st.button("Clear key result", use_container_width=True)

    if clear_btn:
        st.session_state.any_updated_payload = None
        st.session_state.any_updated_count = 0
        st.session_state.any_total_rules = 0
        st.session_state.any_filename = "Rules_updated_key.json"
        st.experimental_rerun()

    if run_btn:
        if not uploaded:
            st.error("Please upload a Rules JSON first.")
        else:
            try:
                payload = read_uploaded_json(uploaded)
                parsed_value: Any = parse_value(raw_value, value_type)
                restrict_ids = parse_param_ids([restrict_raw]) if restrict_raw.strip() else None

                updated_count, total_rules, new_payload = update_key_for_rules(
                    payload,
                    key_path=key_path,
                    new_value=parsed_value,
                    only_missing=only_missing,
                    restrict_param_ids=restrict_ids,
                )

                st.session_state.any_updated_payload = new_payload
                st.session_state.any_updated_count = updated_count
                st.session_state.any_total_rules = total_rules

                base_name = sanitize_filename_base(uploaded.name)
                safe_key = key_path.replace(".", "_")
                value_label = "null" if parsed_value is None else str(parsed_value)
                safe_val = value_label.replace("/", "").replace(" ", "")
                st.session_state.any_filename = f"{base_name}_{safe_key}_{safe_val}.json"

                st.success("Key update complete.")
            except Exception as e:
                st.exception(e)

    if st.session_state.any_updated_payload is not None:
        st.markdown("### Summary")
        st.write(
            f"- Total rules found: **{st.session_state.any_total_rules}**\n"
            f"- Rules updated: **{st.session_state.any_updated_count}**\n"
            f"- Output filename: **{st.session_state.any_filename}**"
        )

        buffer = make_download_buffer(st.session_state.any_updated_payload)
        st.download_button(
            label="Download updated JSON",
            data=buffer,
            file_name=st.session_state.any_filename,
            mime="application/json",
            use_container_width=True,
        )


def render_remove_params_tool() -> None:
    st.subheader("Remove parameter rules by parametertype_id")

    uploaded = st.file_uploader("Upload Rules JSON", type=["json"], key="remove_uploader")

    ids_raw: str = st.text_input(
        "parametertype_id(s) to remove",
        value="",
        placeholder="e.g. 5239, 6001, 7002",
        help="Comma- or space-separated list of IDs. All matching rules will be removed.",
    )

    if "remove_updated_payload" not in st.session_state:
        st.session_state.remove_updated_payload = None
        st.session_state.remove_removed_count = 0
        st.session_state.remove_total_rules = 0
        st.session_state.remove_filename = "Rules_removed_params.json"

    col_run, col_clear = st.columns(2)
    with col_run:
        run_btn = st.button("Remove parameters", type="primary", use_container_width=True)
    with col_clear:
        clear_btn = st.button("Clear removal result", use_container_width=True)

    if clear_btn:
        st.session_state.remove_updated_payload = None
        st.session_state.remove_removed_count = 0
        st.session_state.remove_total_rules = 0
        st.session_state.remove_filename = "Rules_removed_params.json"
        st.experimental_rerun()

    if run_btn:
        if not uploaded:
            st.error("Please upload a Rules JSON first.")
        elif not ids_raw.strip():
            st.error("Please enter at least one parametertype_id.")
        else:
            try:
                payload = read_uploaded_json(uploaded)
                # Parse IDs
                restrict_ids = parse_param_ids([ids_raw])
                if not restrict_ids:
                    st.error("Could not parse any valid integer IDs.")
                else:
                    removed_count, total_rules, new_payload = remove_params_from_payload(
                        payload, sorted(restrict_ids)
                    )
                    st.session_state.remove_updated_payload = new_payload
                    st.session_state.remove_removed_count = removed_count
                    st.session_state.remove_total_rules = total_rules

                    base_name = sanitize_filename_base(uploaded.name)
                    ids_label = "_".join(str(i) for i in sorted(restrict_ids))
                    st.session_state.remove_filename = f"{base_name}_remove_{ids_label}.json"

                    st.success("Parameter removal complete.")
            except Exception as e:
                st.exception(e)

    if st.session_state.remove_updated_payload is not None:
        st.markdown("### Summary")
        st.write(
            f"- Original rules: **{st.session_state.remove_total_rules}**\n"
            f"- Rules removed: **{st.session_state.remove_removed_count}**\n"
            f"- Rules remaining: **{st.session_state.remove_total_rules - st.session_state.remove_removed_count}**\n"
            f"- Output filename: **{st.session_state.remove_filename}**"
        )

        buffer = make_download_buffer(st.session_state.remove_updated_payload)
        st.download_button(
            label="Download updated JSON",
            data=buffer,
            file_name=st.session_state.remove_filename,
            mime="application/json",
            use_container_width=True,
        )


def render_range_calculator_tool() -> None:
    st.subheader("Range calculator (active / limit)")

    col_target, col_type = st.columns(2)
    with col_target:
        target: float = st.number_input(
            "Target value",
            min_value=0.0,
            step=0.1,
            value=12.0,
            format="%.2f",
        )
    with col_type:
        mode: str = st.selectbox(
            "Type",
            options=["active", "limit"],
            index=0,
            help="Use 'active' for actives, 'limit' for limit-style parameters.",
        )

    run_btn = st.button("Calculate ranges", type="primary", use_container_width=True)

    if run_btn:
        if target == 0:
            st.markdown("**Special case (target = 0):**")
            st.code("perfect_range: 0.00\nnot_okay_range: > 0.00", language="text")
            return

        if mode == "active":
            bands: ActiveBands = compute_active_bands(target)
            lines = [
                f"perfect_range: {fmt(bands.low_perfect)} - {fmt(bands.high_perfect)}",
                f"okay_range: {fmt(bands.low_ok)} - {fmt(bands.low_perfect)}",
                f"okay_range_2: {fmt(bands.high_perfect)} - {fmt(bands.high_ok2)}",
                f"not_okay_range: <{fmt(bands.low_ok)} OR >{fmt(bands.high_ok2)}",
            ]
        else:  # mode == "limit"
            threshold_perfect: float = 0.30 * target
            lines = [
                f"perfect_range: <= {fmt(threshold_perfect)}",
                f"okay_range: {fmt(threshold_perfect)} - {fmt(target)}",
                f"not_okay_range: > {fmt(target)}",
            ]

        st.markdown("### Ranges")
        st.code("\n".join(lines), language="text")


# =========================
# Main app
# =========================

def main() -> None:
    st.set_page_config(
        page_title="Rules toolbox",
        page_icon="🧰",
        layout="centered",
    )

    st.title("Rules toolbox 🧰")
    st.caption("Choose a workflow, upload a Rules JSON if needed, and download the updated file.")

    workflow_labels = {
        "spec": "Update spec_id in Rules JSON",
        "unit": "Update DDF_unit in Rules JSON",
        "any": "Update any key (dot-path) in Rules JSON",
        "remove": "Remove rules by parametertype_id",
        "range": "Range calculator (no JSON)",
    }

    selected_label = st.selectbox(
        "Which workflow do you want to run?",
        options=list(workflow_labels.values()),
    )

    reverse_lookup = {v: k for k, v in workflow_labels.items()}
    key = reverse_lookup[selected_label]

    st.markdown("---")

    if key == "spec":
        render_update_spec_id_tool()
    elif key == "unit":
        render_update_unit_tool()
    elif key == "any":
        render_update_any_key_tool()
    elif key == "remove":
        render_remove_params_tool()
    elif key == "range":
        render_range_calculator_tool()
    else:
        st.error("Unknown workflow selection.")


if __name__ == "__main__":
    main()