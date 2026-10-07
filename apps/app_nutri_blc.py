#!/usr/bin/env python3
"""
app_bilacon.py — Nutri Rules Generator for Bilacon (Streamlit)

Generates an Apps Script–compatible Rules JSON payload for Bilacon nutrition
parameters, using per-parameter target values + units and parameter-specific bounds rules.
"""

from __future__ import annotations

import json
import re
import requests 
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# --------------------------- Bilacon Parameter Mapping ---------------------------

@dataclass(frozen=True)
class ParameterSpec:
    parametertype_id: int
    name: str
    group: str  # "locked", "sodium_like", "other"


PARAMETERS: List[ParameterSpec] = [
    # Locked Main Parameters (g/100g enforced)
    ParameterSpec(13810, "Energy value kJ/100g", "locked"),
    ParameterSpec(13811, "Energy value kcal/100g", "locked"),
    ParameterSpec(13804, "Fat", "locked"),
    ParameterSpec(13805, "Sum saturated fatty acids", "locked"),
    ParameterSpec(13809, "Carbohydrates", "locked"),
    ParameterSpec(13808, "Sugar", "locked"),
    ParameterSpec(13803, "Dietary fiber", "locked"),
    ParameterSpec(13814, "Protein", "locked"),
    ParameterSpec(13813, "Salt content", "locked"),

    # Sodium + mono/poly unsaturated fatty acids (Piecewise if g/100g; else dev%)
    ParameterSpec(13806, "Sum monounsaturated fatty acids", "sodium_like"),
    ParameterSpec(13807, "Sum polyunsaturated fatty acids", "sodium_like"),
    ParameterSpec(13812, "Sodium", "sodium_like"),

    # Other parameters (Default to percentage deviation)
    ParameterSpec(13815, "Glucose", "other"),
    ParameterSpec(13816, "Fructose", "other"),
    ParameterSpec(13817, "Sucrose", "other"),
    ParameterSpec(13818, "Maltose", "other"),
    ParameterSpec(13819, "Lactose", "other"),
    ParameterSpec(13802, "Ash", "other"),
    ParameterSpec(13800, "Dry matter", "other"),
    ParameterSpec(13801, "Water", "other"),
]

LOCKED_UNIT: str = "g/100g"

# Parameter ID sets for logic lookups
OTHER_PARAM_IDS: set[int] = {
    13815, 13816, 13817, 13818, 13819, 13802, 13800, 13801
}

SODIUM_LIKE_IDS: set[int] = {13806, 13807, 13812}


# --------------------------- Helpers: Decimals & Formatting ---------------------------

Q4 = Decimal("0.0001")


def q4(x: Decimal) -> Decimal:
    """Quantize to 4dp with half-up rounding."""
    return x.quantize(Q4, rounding=ROUND_HALF_UP)


def clamp_lower_to_zero(x: Decimal) -> Decimal:
    return x if x >= Decimal("0") else Decimal("0")


# --------------------------- Parsing Numeric Inputs ---------------------------

@dataclass
class ParsedNumber:
    value: Optional[Decimal]          # parsed numeric value (or None)
    extracted_unit: Optional[str]     # extracted unit letters, e.g. "mg"
    had_unit_text: bool               # True if we stripped letters from target input
    error: Optional[str]              # parse error if any


_UNIT_RE = re.compile(r"^\s*([+-]?[0-9][0-9.,\s]*)\s*([A-Za-zµ/%]+)?\s*$")


def parse_number_with_locale_and_unit(raw: str) -> ParsedNumber:
    """
    Parse a numeric string that may contain thousands/decimal separators and optional unit text.
    Handles both EU (1.500,2) and US (1,500.2) formats seamlessly.
    """
    s = (raw or "").strip()
    if s == "" or s.lower() == "null":
        return ParsedNumber(value=None, extracted_unit=None, had_unit_text=False, error=None)

    m = _UNIT_RE.match(s)
    if not m:
        return ParsedNumber(value=None, extracted_unit=None, had_unit_text=False, error="Could not parse number format.")

    num_part = (m.group(1) or "").replace(" ", "")
    unit_part = m.group(2)
    had_unit_text = unit_part is not None and unit_part.strip() != ""

    # Normalize separators
    if "." in num_part and "," in num_part:
        dot_i = num_part.find(".")
        comma_i = num_part.find(",")
        if dot_i < comma_i:
            # EU: '.' thousands, ',' decimal
            normalized = num_part.replace(".", "").replace(",", ".")
        else:
            # US: ',' thousands, '.' decimal
            normalized = num_part.replace(",", "")
    elif "." in num_part:
        if re.search(r"\.\d{3}$", num_part):
            normalized = num_part.replace(".", "")
        else:
            normalized = num_part
    elif "," in num_part:
        if re.search(r",\d{3}$", num_part):
            normalized = num_part.replace(",", "")
        else:
            normalized = num_part.replace(",", ".")
    else:
        normalized = num_part

    try:
        val = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return ParsedNumber(value=None, extracted_unit=unit_part, had_unit_text=had_unit_text, error="Invalid numeric value.")

    return ParsedNumber(value=val, extracted_unit=(unit_part.strip() if unit_part else None), had_unit_text=had_unit_text, error=None)


# --------------------------- Deviation Rules ---------------------------

def deviation_energy(target: Decimal) -> Decimal:
    return q4(target * Decimal("0.20"))


def deviation_piecewise_10_40(target: Decimal, low_abs: Decimal, high_abs: Decimal) -> Decimal:
    """
    <10 -> ±low_abs
    10..40 inclusive -> ±20% of target
    >40 -> ±high_abs
    """
    if target < Decimal("10"):
        return q4(low_abs)
    if target <= Decimal("40"):
        return q4(target * Decimal("0.20"))
    return q4(high_abs)


def deviation_saturated_like(target: Decimal, threshold: Decimal, low_abs: Decimal) -> Decimal:
    """<threshold -> ±low_abs else ±20%."""
    if target < threshold:
        return q4(low_abs)
    return q4(target * Decimal("0.20"))


def deviation_percent(target: Decimal, percent: Decimal) -> Decimal:
    return q4(target * (percent / Decimal("100")))


def compute_bounds(target: Decimal, dev: Decimal) -> Tuple[Decimal, Decimal]:
    lower = clamp_lower_to_zero(q4(target - dev))
    upper = q4(target + dev)
    return lower, upper


# --------------------------- Payload Generation ---------------------------

def rule_row(
    *,
    spec_id: int,
    parametertype_id: int,
    ddf_target_value: Optional[Decimal],
    ddf_unit: Optional[str],
    ddf_type: str,
    color: str,
    operator: str,
    value: Any,
    linker: Optional[str],
    operator2: Optional[str],
    value2: Optional[Any],
) -> Dict[str, Any]:
    """Build one rule entry formatted for LIMS payload."""
    data: Dict[str, Any] = {
        "color": color,
        "column": 0,
        "DDF_target_value": (float(q4(ddf_target_value)) if ddf_target_value is not None else None),
        "DDF_type": ddf_type,
        "DDF_unit": (ddf_unit if (ddf_unit is not None and str(ddf_unit).strip() != "") else None),
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
    return {"action": "create", "data": data}


def build_rules_payload(
    *,
    spec_id: int,
    per_param_target: Dict[int, Optional[Decimal]],
    per_param_unit: Dict[int, Optional[str]],
    per_param_deviation_percent: Dict[int, Optional[Decimal]],
    removed_params: set[int],
) -> Tuple[Dict[str, Any], List[str]]:
    """Generates rules payload and returns (payload, warnings)."""
    warnings: List[str] = []
    rules: List[Dict[str, Any]] = []

    for p in PARAMETERS:
        if p.parametertype_id in removed_params:
            continue

        target = per_param_target.get(p.parametertype_id)
        unit = per_param_unit.get(p.parametertype_id)

        # Empty target => perfect != rule with literal '""'
        if target is None:
            rules.append(
                rule_row(
                    spec_id=spec_id,
                    parametertype_id=p.parametertype_id,
                    ddf_target_value=None,
                    ddf_unit=unit,
                    ddf_type="perfect",
                    color="green",
                    operator="!=",
                    value='""',
                    linker=None,
                    operator2=None,
                    value2=None,
                )
            )
            continue

        dev: Optional[Decimal] = None

        # Bilacon locked main parameters mapping
        if p.group == "locked":
            if p.parametertype_id in (13810, 13811):  # Energy kJ / kcal
                dev = deviation_energy(target)
            elif p.parametertype_id == 13804:  # Fat total
                dev = deviation_piecewise_10_40(target, low_abs=Decimal("1.5"), high_abs=Decimal("8"))
            elif p.parametertype_id == 13805:  # Saturated fatty acids
                dev = deviation_saturated_like(target, threshold=Decimal("4"), low_abs=Decimal("0.8"))
            elif p.parametertype_id in (13809, 13808, 13803, 13814):  # Carbs / Sugar / Fiber / Protein
                dev = deviation_piecewise_10_40(target, low_abs=Decimal("2"), high_abs=Decimal("8"))
            elif p.parametertype_id == 13813:  # Salt content
                dev = deviation_saturated_like(target, threshold=Decimal("1.25"), low_abs=Decimal("0.375"))
            else:
                warnings.append(f"{p.name}: no deviation rule defined for locked parameter; used flat 20%.")
                dev = q4(target * Decimal("0.20"))

        elif p.group == "sodium_like":
            if (unit or "").strip() == LOCKED_UNIT:
                if p.parametertype_id == 13812:  # Sodium
                    dev = deviation_saturated_like(target, threshold=Decimal("0.5"), low_abs=Decimal("0.15"))
                else:  # Mono / Poly unsaturated
                    dev = deviation_saturated_like(target, threshold=Decimal("4"), low_abs=Decimal("0.8"))
            else:
                perc = per_param_deviation_percent.get(p.parametertype_id)
                if perc is None:
                    warnings.append(f"{p.name}: unit is not '{LOCKED_UNIT}', so deviation% is required. Defaulted to 10%.")
                    perc = Decimal("10")
                dev = deviation_percent(target, perc)

        else:
            # Other parameters
            perc = per_param_deviation_percent.get(p.parametertype_id)
            if perc is None:
                warnings.append(f"{p.name}: deviation% not provided. Defaulted to 10%.")
                perc = Decimal("10")
            dev = deviation_percent(target, perc)

        lower, upper = compute_bounds(target, dev)

        # Perfect
        rules.append(
            rule_row(
                spec_id=spec_id,
                parametertype_id=p.parametertype_id,
                ddf_target_value=target,
                ddf_unit=unit,
                ddf_type="perfect",
                color="green",
                operator=">=",
                value=float(lower),
                linker="AND",
                operator2="<=",
                value2=float(upper),
            )
        )
        # Not OK
        rules.append(
            rule_row(
                spec_id=spec_id,
                parametertype_id=p.parametertype_id,
                ddf_target_value=target,
                ddf_unit=unit,
                ddf_type="not OK",
                color="red",
                operator="<",
                value=float(lower),
                linker="OR",
                operator2=">",
                value2=float(upper),
            )
        )

    return {"rules": rules}, warnings


# --------------------------- Streamlit UI ---------------------------

def main() -> None:
    st.set_page_config(page_title="Nutri Rules Generator (Bilacon)", layout="wide")
    st.title("Nutri Rules Generator (Bilacon)")
    st.caption("Generate Apps Script–compatible Rules JSON for Bilacon nutrition specs.")

    if "removed_params" not in st.session_state:
        st.session_state.removed_params = set()

    with st.sidebar:
        st.subheader("Global")
        spec_id_raw = st.text_input("spec_id", value="", placeholder="e.g. 1205")
        
        st.write("")
        if st.button("🔄 Restore All Parameters", help="Bring back any removed parameters"):
            st.session_state.removed_params = set()
            st.rerun()

        st.write("")
        st.subheader("Output")
        file_prefix = st.text_input("Filename prefix", value="Bilacon_Rules", help="Used for the download file name.")
        show_preview = st.checkbox("Show computed bounds preview table", value=True)

    spec_id: Optional[int] = None
    spec_id_err: Optional[str] = None
    if spec_id_raw.strip() == "":
        spec_id_err = "spec_id is required."
    else:
        try:
            spec_id = int(float(spec_id_raw.strip()))
        except Exception:
            spec_id_err = "spec_id must be an integer."

    if spec_id_err:
        st.error(spec_id_err)

    st.markdown("### Parameter targets & units")

    per_param_target: Dict[int, Optional[Decimal]] = {}
    per_param_unit: Dict[int, Optional[str]] = {}
    per_param_dev: Dict[int, Optional[Decimal]] = {}

    input_notes: List[str] = []
    parse_errors: List[str] = []

    header_cols = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
    header_cols[0].markdown("**Parameter (parametertype_id)**")
    header_cols[1].markdown("**Target**")
    header_cols[2].markdown("**Unit**")
    header_cols[3].markdown("**Deviation %**")

    for p in PARAMETERS:
        if p.parametertype_id in st.session_state.removed_params:
            continue

        cols = st.columns([3.5, 1.5, 1.5, 1.5, 0.5])
        cols[0].write(f"{p.name}  \n`{p.parametertype_id}`")

        target_key = f"target_{p.parametertype_id}"
        unit_key = f"unit_{p.parametertype_id}"
        dev_key = f"dev_{p.parametertype_id}"

        raw_target = cols[1].text_input(
            label="",
            key=target_key,
            value=st.session_state.get(target_key, ""),
            placeholder="null / empty allowed",
        )

        if p.group == "locked":
            unit_val = LOCKED_UNIT
            cols[2].write(LOCKED_UNIT)
        elif p.group == "sodium_like":
            unit_choice = cols[2].selectbox(
                label="",
                options=[LOCKED_UNIT, "mg/100g", "mg", "g", "other..."],
                index=0,
                key=f"{unit_key}_choice",
            )
            if unit_choice == "other...":
                unit_val = cols[2].text_input(
                    label="",
                    key=unit_key,
                    value=st.session_state.get(unit_key, ""),
                    placeholder="type unit",
                )
            else:
                unit_val = unit_choice
        else:
            unit_val = cols[2].text_input(
                label="",
                key=unit_key,
                value=st.session_state.get(unit_key, ""),
                placeholder="optional",
            )

        parsed = parse_number_with_locale_and_unit(raw_target)

        if parsed.error:
            if raw_target.strip() != "":
                parse_errors.append(f"{p.name}: {parsed.error} (input: {raw_target})")
            per_param_target[p.parametertype_id] = None
        else:
            per_param_target[p.parametertype_id] = parsed.value

        if parsed.had_unit_text and p.group == "locked":
            input_notes.append(f"{p.name}: unit text was removed from target. Note: units must be {LOCKED_UNIT}.")

        if parsed.had_unit_text and p.group != "locked" and (unit_val is None or str(unit_val).strip() == ""):
            if parsed.extracted_unit:
                input_notes.append(
                    f"{p.name}: detected unit '{parsed.extracted_unit}' in target input. Consider entering it in the Unit field."
                )

        per_param_unit[p.parametertype_id] = (unit_val.strip() if isinstance(unit_val, str) and unit_val.strip() != "" else unit_val)

        needs_dev = False
        if p.parametertype_id in OTHER_PARAM_IDS:
            needs_dev = True
        if p.parametertype_id in SODIUM_LIKE_IDS and (per_param_unit[p.parametertype_id] or "").strip() != LOCKED_UNIT:
            needs_dev = True

        if needs_dev and per_param_target[p.parametertype_id] is not None:
            dev_str = cols[3].text_input(
                label="",
                key=dev_key,
                value=st.session_state.get(dev_key, ""),
                placeholder="0–50",
            )
            dev_str = (dev_str or "").strip()
            if dev_str == "":
                per_param_dev[p.parametertype_id] = None
                cols[3].markdown("<div style='margin-top:6px;'>%</div>", unsafe_allow_html=True)
            else:
                try:
                    dev_val = Decimal(dev_str)
                    if dev_val < Decimal("0") or dev_val > Decimal("50"):
                        parse_errors.append(f"{p.name}: deviation% must be between 0 and 50.")
                        per_param_dev[p.parametertype_id] = None
                    else:
                        per_param_dev[p.parametertype_id] = dev_val
                    cols[3].markdown("<div style='margin-top:6px;'>%</div>", unsafe_allow_html=True)
                except Exception:
                    parse_errors.append(f"{p.name}: deviation% is not a valid number.")
                    per_param_dev[p.parametertype_id] = None
                    cols[3].markdown("<div style='margin-top:6px;'>%</div>", unsafe_allow_html=True)
        else:
            cols[3].write("—")
            per_param_dev[p.parametertype_id] = None

        if cols[4].button("➖", key=f"remove_{p.parametertype_id}", help="Remove parameter"):
            st.session_state.removed_params.add(p.parametertype_id)
            st.rerun()

    if input_notes:
        st.warning("\n".join(input_notes))

    if parse_errors:
        st.error("Fix these issues before generating JSON:\n- " + "\n- ".join(parse_errors))

    st.markdown("### Generate")
    can_generate = (spec_id is not None) and (not parse_errors)

    generate_clicked = st.button("Generate Rules JSON", type="primary", disabled=not can_generate)

    if generate_clicked and spec_id is not None and not parse_errors:
        payload, warnings = build_rules_payload(
            spec_id=spec_id,
            per_param_target=per_param_target,
            per_param_unit=per_param_unit,
            per_param_deviation_percent=per_param_dev,
            removed_params=st.session_state.removed_params,
        )

        if warnings:
            st.warning("\n".join(warnings))

        if show_preview:
            st.markdown("### Preview (computed bounds)")
            preview_rows: List[Dict[str, Any]] = []
            for item in payload["rules"]:
                d = item["data"]
                preview_rows.append(
                    {
                        "parametertype_id": d["parametertype_id"],
                        "DDF_type": d["DDF_type"],
                        "unit": d["DDF_unit"],
                        "target": d["DDF_target_value"],
                        "operator": d["operator"],
                        "value": d["value"],
                        "linker": d["linker"],
                        "operator2": d["operator2"],
                        "value2": d["value2"],
                        "color": d["color"],
                    }
                )
            st.dataframe(preview_rows, use_container_width=True, height=420)

        now = datetime.now()
        fname = f"{file_prefix}_{spec_id}_{now.strftime('%Y%m%d_%H%M')}.json"
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        
        st.session_state["nutri_json_bytes"] = json_bytes
        st.session_state["nutri_fname"] = fname
        st.session_state["nutri_rules_count"] = len(payload['rules'])
        st.session_state["nutri_payload_dict"] = payload

    if "nutri_json_bytes" in st.session_state:
        st.success(f"Generated {st.session_state['nutri_rules_count']} rules.")
        
        col1, col2 = st.columns([1, 4])
        
        with col1:
            st.download_button(
                label="Download Rules JSON",
                data=st.session_state["nutri_json_bytes"],
                file_name=st.session_state["nutri_fname"],
                mime="application/json",
            )
            
        with col2:
            if st.button("🚀 Send to LIMS"):
                webhook_url = "https://n8n.sunday.de/webhook/ccdc1813-7461-4926-804d-a8bc2bf5a601"
                try:
                    with st.spinner("Sending payload..."):
                        response = requests.post(webhook_url, json=st.session_state["nutri_payload_dict"])
                        response.raise_for_status()
                    st.success("Successfully sent to n8n!")
                except Exception as e:
                    st.error(f"Failed to send to n8n: {e}")

    st.markdown("---")
    st.caption("Configured for Bilacon lab parameter IDs.")


if __name__ == "__main__":
    main()