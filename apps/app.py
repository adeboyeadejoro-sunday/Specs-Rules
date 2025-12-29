#!/usr/bin/env python3
"""
Streamlit UI for generate_standalone_rules.py (CLI behavior preserved strictly)

- Dynamic form rows (add/remove params)
- In-memory JSON generation + Download button
- Same rule-building logic as the CLI version
- Dummy mode keeps value='""' (literal quotes) as required by LIMS
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast

import streamlit as st

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


# -----------------------------
# Types
# -----------------------------

Mode = Literal["active", "mineral", "limit3", "limit2", "qualitative", "dummy"]


@dataclass(frozen=True)
class ParamSpec:
    parametertype_id: int
    target: Optional[float]
    unit: Optional[str]
    mode: Mode


class ParamRow(TypedDict):
    parametertype_id: int
    mode: Mode
    target_is_null: bool
    target_value: float
    unit_is_null: bool
    unit_value: str


# -----------------------------
# Helpers (same as CLI script)
# -----------------------------

def r2(x: float) -> float:
    return round(x, 2)


def base_data(
    *,
    parametertype_id: int,
    spec_id: int,
    unit: Optional[str],
    target: Optional[float],
    ddf_type: Literal["perfect", "OK", "not OK"],
    color: Literal["green", "orange", "red"],
    operator: Optional[str],
    value: Any,
    operator2: Optional[str] = None,
    value2: Any = None,
    linker: Optional[Literal["AND", "OR"]] = None,
) -> Dict[str, Any]:
    return {
        "color": color,
        "column": 0,
        "DDF_target_value": target,
        "DDF_type": ddf_type,
        "DDF_unit": unit,
        "inverse": 0,
        "linker": linker,
        "operator": operator,
        "operator2": operator2,
        "parametertype_id": parametertype_id,
        "regex_filter": None,
        "show": 1,
        "spec_id": spec_id,
        "text": None,
        "translations": None,
        "value": value,
        "value2": value2,
    }


def make_rule(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"action": "create", "data": data}


# -----------------------------
# Band calculation
# -----------------------------

@dataclass(frozen=True)
class ActiveBands:
    low_ok: float
    low_perfect: float
    high_perfect: float
    high_ok2: float


def compute_active_bands(target: float) -> ActiveBands:
    return ActiveBands(
        low_ok=r2(0.80 * target),
        low_perfect=r2(0.90 * target),
        high_perfect=r2(1.25 * target),
        high_ok2=r2(1.50 * target),
    )


def compute_mineral_bands(target: float) -> ActiveBands:
    return ActiveBands(
        low_ok=r2(0.80 * target),
        low_perfect=r2(0.90 * target),
        high_perfect=r2(1.25 * target),
        high_ok2=r2(1.45 * target),  # mineral-specific change
    )


# -----------------------------
# Rule builders (same behavior)
# -----------------------------

def build_active_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    if t == 0:
        perfect = make_rule(
            base_data(
                parametertype_id=pid,
                spec_id=spec_id,
                unit=unit,
                target=t,
                ddf_type="perfect",
                color="green",
                operator="<=",
                value=0.0,
            )
        )
        not_ok = make_rule(
            base_data(
                parametertype_id=pid,
                spec_id=spec_id,
                unit=unit,
                target=t,
                ddf_type="not OK",
                color="red",
                operator=">",
                value=0.0,
            )
        )
        return [perfect, not_ok]

    b = compute_active_bands(t)

    perfect = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator=">=",
            operator2="<=",
            linker="AND",
            value=b.low_perfect,
            value2=b.high_perfect,
        )
    )

    ok_low = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="OK",
            color="orange",
            operator=">=",
            operator2="<",
            linker="AND",
            value=b.low_ok,
            value2=b.low_perfect,
        )
    )

    ok_high = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="OK",
            color="orange",
            operator=">",
            operator2="<=",
            linker="AND",
            value=b.high_perfect,
            value2=b.high_ok2,
        )
    )

    not_ok = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator="<",
            operator2=">",
            linker="OR",
            value=b.low_ok,
            value2=b.high_ok2,
        )
    )

    return [perfect, ok_low, ok_high, not_ok]


def build_mineral_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    if t == 0:
        perfect = make_rule(
            base_data(
                parametertype_id=pid,
                spec_id=spec_id,
                unit=unit,
                target=t,
                ddf_type="perfect",
                color="green",
                operator="<=",
                value=0.0,
            )
        )
        not_ok = make_rule(
            base_data(
                parametertype_id=pid,
                spec_id=spec_id,
                unit=unit,
                target=t,
                ddf_type="not OK",
                color="red",
                operator=">",
                value=0.0,
            )
        )
        return [perfect, not_ok]

    b = compute_mineral_bands(t)

    perfect = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator=">=",
            operator2="<=",
            linker="AND",
            value=b.low_perfect,
            value2=b.high_perfect,
        )
    )

    ok_low = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="OK",
            color="orange",
            operator=">=",
            operator2="<",
            linker="AND",
            value=b.low_ok,
            value2=b.low_perfect,
        )
    )

    ok_high = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="OK",
            color="orange",
            operator=">",
            operator2="<=",
            linker="AND",
            value=b.high_perfect,
            value2=b.high_ok2,
        )
    )

    not_ok = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator="<",
            operator2=">",
            linker="OR",
            value=b.low_ok,
            value2=b.high_ok2,
        )
    )

    return [perfect, ok_low, ok_high, not_ok]


def build_limit3_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    if t == 0:
        perfect = make_rule(
            base_data(
                parametertype_id=pid,
                spec_id=spec_id,
                unit=unit,
                target=t,
                ddf_type="perfect",
                color="green",
                operator="<=",
                value=0.0,
            )
        )
        not_ok = make_rule(
            base_data(
                parametertype_id=pid,
                spec_id=spec_id,
                unit=unit,
                target=t,
                ddf_type="not OK",
                color="red",
                operator=">",
                value=0.0,
            )
        )
        return [perfect, not_ok]

    threshold_perfect = r2(0.30 * t)

    perfect = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator="<=",
            value=threshold_perfect,
        )
    )

    ok = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="OK",
            color="orange",
            operator=">=",
            operator2="<=",
            linker="AND",
            value=threshold_perfect,
            value2=r2(t),
        )
    )

    not_ok = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator=">",
            value=r2(t),
        )
    )

    return [perfect, ok, not_ok]


def build_limit2_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    perfect = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator="<=",
            value=r2(t),
        )
    )

    not_ok = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator=">",
            value=r2(t),
        )
    )

    return [perfect, not_ok]


def build_qualitative_rules(
    ps: ParamSpec, spec_id: int, qual_en: str, qual_de: str
) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    perfect = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator="=",
            operator2="=",
            linker="OR",
            value=qual_en,
            value2=qual_de,
        )
    )

    not_ok = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator=">",
            value=r2(t),
        )
    )

    return [perfect, not_ok]


def build_dummy_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id

    rule = make_rule(
        base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=None,
            target=None,
            ddf_type="perfect",
            color="green",
            operator="!=",
            value='""',  # keep literal quotes as required by LIMS
        )
    )
    return [rule]


# -----------------------------
# Streamlit state helpers
# -----------------------------

def default_row() -> ParamRow:
    return {
        "parametertype_id": 0,
        "mode": "active",
        "target_is_null": False,
        "target_value": 0.0,
        "unit_is_null": False,
        "unit_value": "",
    }


def get_berlin_now() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("Europe/Berlin"))


def to_param_spec(row: ParamRow) -> ParamSpec:
    target: Optional[float]
    unit: Optional[str]

    if row["mode"] == "dummy":
        target = None
        unit = None
    else:
        target = None if row["target_is_null"] else float(row["target_value"])
        unit = None if row["unit_is_null"] else (row["unit_value"] if row["unit_value"] != "" else "")

    return ParamSpec(
        parametertype_id=int(row["parametertype_id"]),
        target=target,
        unit=unit if unit != "" else (None if row["unit_is_null"] else ""),
        mode=row["mode"],
    )


def validate_inputs(spec_id: int, rows: List[ParamRow], qual_en: str, qual_de: str) -> List[str]:
    errors: List[str] = []

    if spec_id <= 0:
        errors.append("spec_id must be a positive integer.")

    if len(rows) == 0:
        errors.append("Add at least one parameter row.")

    for i, row in enumerate(rows, start=1):
        pid = row["parametertype_id"]
        mode = row["mode"]

        if int(pid) <= 0:
            errors.append(f"Row {i}: parametertype_id must be a positive integer.")

        # Match CLI behavior strictly
        if mode in ("active", "mineral", "limit3", "limit2", "qualitative"):
            if row["target_is_null"]:
                errors.append(f"Row {i}: {mode} requires numeric target (target cannot be null).")

        if mode == "qualitative":
            if qual_en == "" or qual_de == "":
                errors.append("Qualitative mode requires both qual_en and qual_de (non-empty).")

        # Dummy: target/unit ignored; no validation needed beyond pid

    return errors


def build_rules_from_specs(spec_id: int, param_specs: List[ParamSpec], qual_en: str, qual_de: str) -> List[Dict[str, Any]]:
    all_rules: List[Dict[str, Any]] = []

    for ps in param_specs:
        if ps.mode == "active":
            if ps.target is None:
                raise ValueError("Active requires numeric target.")
            rules = build_active_rules(ps, spec_id)

        elif ps.mode == "mineral":
            if ps.target is None:
                raise ValueError("Mineral requires numeric target.")
            rules = build_mineral_rules(ps, spec_id)

        elif ps.mode == "limit3":
            if ps.target is None:
                raise ValueError("Limit3 requires numeric target.")
            rules = build_limit3_rules(ps, spec_id)

        elif ps.mode == "limit2":
            if ps.target is None:
                raise ValueError("Limit2 requires numeric target.")
            rules = build_limit2_rules(ps, spec_id)

        elif ps.mode == "qualitative":
            if ps.target is None:
                raise ValueError("Qualitative requires numeric target.")
            rules = build_qualitative_rules(ps, spec_id, qual_en, qual_de)

        elif ps.mode == "dummy":
            rules = build_dummy_rules(ps, spec_id)

        else:
            raise ValueError(f"Unsupported mode: {ps.mode}")

        all_rules.extend(rules)

    return all_rules


def rule_count_for(ps: ParamSpec) -> int:
    if ps.mode in ("active", "mineral", "limit3"):
        if ps.target == 0:
            return 2
    if ps.mode in ("active", "mineral"):
        return 4
    if ps.mode == "limit3":
        return 3
    if ps.mode in ("limit2", "qualitative"):
        return 2
    if ps.mode == "dummy":
        return 1
    return 0


# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="Standalone Rules Generator", layout="wide")
st.title("Standalone Rules Generator")

if "rows" not in st.session_state:
    st.session_state["rows"] = [default_row()]
if "generated_json" not in st.session_state:
    st.session_state["generated_json"] = None
if "generated_filename" not in st.session_state:
    st.session_state["generated_filename"] = None
if "generated_rules_count" not in st.session_state:
    st.session_state["generated_rules_count"] = 0

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("Inputs")

    spec_id: int = st.number_input("spec_id", min_value=0, step=1, value=0)

    rows: List[ParamRow] = cast(List[ParamRow], st.session_state["rows"])

    # If any row is qualitative, show qual inputs
    any_qual = any(r["mode"] == "qualitative" for r in rows)
    qual_en = ""
    qual_de = ""
    if any_qual:
        st.markdown("**Qualitative texts (required because at least one row is qualitative):**")
        qual_en = st.text_input("qual_en (EN)", value="")
        qual_de = st.text_input("qual_de (DE)", value="")

    st.divider()
    st.markdown("**Parameters**")

    # Render each row
    for idx, row in enumerate(rows):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.6, 0.8])

            row["parametertype_id"] = c1.number_input(
                f"parametertype_id (row {idx+1})",
                min_value=0,
                step=1,
                value=int(row["parametertype_id"]),
                key=f"pid_{idx}",
            )

            row["mode"] = cast(
                Mode,
                c2.selectbox(
                    f"mode (row {idx+1})",
                    options=["active", "mineral", "limit3", "limit2", "qualitative", "dummy"],
                    index=["active", "mineral", "limit3", "limit2", "qualitative", "dummy"].index(row["mode"]),
                    key=f"mode_{idx}",
                ),
            )

            # target input (disabled for dummy)
            if row["mode"] == "dummy":
                row["target_is_null"] = True
                row["target_value"] = 0.0
                c3.caption("target (dummy ignores target/unit)")
                c3.text("dummy: target=null, unit=null")
            else:
                tcol1, tcol2 = c3.columns([1, 1])
                row["target_is_null"] = tcol1.checkbox(
                    "target is null",
                    value=bool(row["target_is_null"]),
                    key=f"t_null_{idx}",
                )
                row["target_value"] = tcol2.number_input(
                    "target value",
                    value=float(row["target_value"]),
                    step=0.01,
                    format="%.6f",
                    disabled=bool(row["target_is_null"]),
                    key=f"t_val_{idx}",
                )

            # unit input (disabled for dummy)
            if row["mode"] == "dummy":
                row["unit_is_null"] = True
                row["unit_value"] = ""
            else:
                ucol1, ucol2 = c4.columns([1, 1])
                row["unit_is_null"] = ucol1.checkbox(
                    "unit null",
                    value=bool(row["unit_is_null"]),
                    key=f"u_null_{idx}",
                )
                row["unit_value"] = ucol2.text_input(
                    "unit",
                    value=str(row["unit_value"]),
                    disabled=bool(row["unit_is_null"]),
                    key=f"u_val_{idx}",
                )

            # Remove row button
            rm_col = st.columns([1, 1, 6])[0]
            if rm_col.button("Remove row", key=f"rm_{idx}", disabled=(len(rows) == 1)):
                rows.pop(idx)
                st.session_state["rows"] = rows
                st.rerun()

    st.write("")
    add1, add2, _ = st.columns([1, 1, 6])
    if add1.button("Add row"):
        rows.append(default_row())
        st.session_state["rows"] = rows
        st.rerun()

    if add2.button("Reset"):
        st.session_state["rows"] = [default_row()]
        st.session_state["generated_json"] = None
        st.session_state["generated_filename"] = None
        st.session_state["generated_rules_count"] = 0
        st.rerun()

    st.divider()

    if st.button("Generate JSON"):
        errs = validate_inputs(spec_id, rows, qual_en, qual_de)
        if errs:
            for e in errs:
                st.error(e)
        else:
            param_specs = [to_param_spec(r) for r in rows]
            # Preserve CLI behavior: qualitative requires --qual EN DE
            if any(ps.mode == "qualitative" for ps in param_specs) and (qual_en == "" or qual_de == ""):
                st.error("Qualitative mode requires both qual_en and qual_de (non-empty).")
            else:
                rules = build_rules_from_specs(spec_id, param_specs, qual_en, qual_de)
                payload = {"rules": rules}
                json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

                now = get_berlin_now()
                filename = f"Rules_{spec_id}_{now:%Y%m%d_%H%M}.json"

                st.session_state["generated_json"] = json_bytes
                st.session_state["generated_filename"] = filename
                st.session_state["generated_rules_count"] = len(rules)

                st.success(f"Generated {len(rules)} rules.")

with right:
    st.subheader("Output")

    generated: Optional[bytes] = st.session_state.get("generated_json")
    filename: Optional[str] = st.session_state.get("generated_filename")
    rules_count: int = int(st.session_state.get("generated_rules_count", 0))

    if generated and filename:
        st.download_button(
            label=f"Download {filename}",
            data=generated,
            file_name=filename,
            mime="application/json",
        )
        st.caption(f"Rules count: {rules_count}")

        # Preview JSON (parsed)
        try:
            parsed = json.loads(generated.decode("utf-8"))
            st.json(parsed)
        except Exception as e:
            st.warning(f"Could not parse JSON for preview: {e}")
    else:
        st.info("Generate JSON to enable download and preview.")
