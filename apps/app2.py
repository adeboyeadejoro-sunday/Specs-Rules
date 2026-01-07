#!/usr/bin/env python3
"""
app.py — Nutri Rules Generator (Streamlit)

Generates an Apps Script–compatible Rules JSON payload for a fixed set of nutrition
parameters, using per-parameter target values + units and parameter-specific bounds rules.

Key specs implemented (from your requirements)
- Rules generation is the default (Specs generation omitted for now).
- Fixed parameter display order and fixed parametertype_id mapping.
- Constants always present: show=1, column=0, inverse=0; regex_filter/text/translations default null.
- If target is empty/null -> generate ONE perfect rule with operator != and value set to the literal string '""'.
- If target exists -> generate perfect + not OK rules with computed bounds.
- Unit locking: for 9 main parameters unit is forced to g/100g and cannot be changed.
- Sodium + mono/poly: if unit is g/100g use piecewise rules; otherwise use deviation% (user provided) instead.
- “Other parameters”: if target exists use deviation% per parameter; default 10% with warning if missing.
- Parsing/normalization:
  * Strip text units from target like '200mg' -> 200; show note if this happened on locked-unit rows.
  * Handle EU/US thousands/decimal formats including '1.500,2' and '1,500.2'
- Rounding/display: UI shows 4dp; payload emits JSON numbers (no trailing zeros needed).
- Clamp negative lower bounds to 0.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# --------------------------- Fixed parameter mapping ---------------------------

@dataclass(frozen=True)
class ParameterSpec:
    parametertype_id: int
    name: str
    group: str  # "locked", "sodium_like", "other"


PARAMETERS: List[ParameterSpec] = [
    ParameterSpec(11709, "Energy value in kJ (protein = N x 6.25)", "locked"),
    ParameterSpec(11710, "Energy value in kcal (protein = N x 6.25)", "locked"),
    ParameterSpec(5239, "Fat, Total", "locked"),
    ParameterSpec(5444, "Fatty acid, saturated", "locked"),
    ParameterSpec(5244, "Carbohydrates*", "locked"),
    ParameterSpec(5245, "Sugar", "locked"),
    ParameterSpec(5252, "Fibre", "locked"),
    ParameterSpec(11423, "Protein, N x 6.25", "locked"),
    ParameterSpec(11440, "Salt from sodium", "locked"),

    ParameterSpec(5240, "Fatty acid*", "other"),
    ParameterSpec(5246, "Sugar, total", "other"),
    ParameterSpec(5247, "Fructose", "other"),
    ParameterSpec(5248, "Glucose", "other"),
    ParameterSpec(5249, "Sucrose", "other"),
    ParameterSpec(5250, "Maltose", "other"),
    ParameterSpec(5251, "Lactose", "other"),

    # Sodium + mono/poly have special behavior: use piecewise rules only if unit is g/100g.
    ParameterSpec(5445, "Fatty acid, monounsaturated", "sodium_like"),
    ParameterSpec(5446, "Fatty acid, polyunsaturated", "sodium_like"),
    ParameterSpec(5299, "Sodium_10873", "sodium_like"),

    ParameterSpec(11249, "Ash", "other"),
    ParameterSpec(11377, "Air humidity", "other"),
    ParameterSpec(12016, "moisture", "other"),
]

LOCKED_UNIT: str = "g/100g"

# “Other parameters” set (exactly as you listed)
OTHER_PARAM_IDS: set[int] = {
    5240, 5246, 5247, 5248, 5249, 5250, 5251, 11249, 11377, 12016
}

SODIUM_LIKE_IDS: set[int] = {5299, 5445, 5446}


# --------------------------- Helpers: decimals & formatting ---------------------------

Q4 = Decimal("0.0001")


def q4(x: Decimal) -> Decimal:
    """Quantize to 4dp with half-up rounding."""
    return x.quantize(Q4, rounding=ROUND_HALF_UP)


def dec_from_floatish(x: Decimal) -> Decimal:
    """Ensure Decimal stays Decimal (placeholder for readability)."""
    return x


def clamp_lower_to_zero(x: Decimal) -> Decimal:
    return x if x >= Decimal("0") else Decimal("0")


# --------------------------- Parsing numeric inputs ---------------------------

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

    Rules:
    - If both '.' and ',' appear:
        * '.' before ',' -> EU thousands + decimal: '1.500,2' -> 1500.2
        * ',' before '.' -> US thousands + decimal: '1,500.2' -> 1500.2
    - If only one separator appears:
        * '1.500' (dot + 3 digits) -> 1500
        * '1,500' (comma + 3 digits) -> 1500
        * '1,5' -> 1.5
    - Strips whitespace inside numbers.
    - Extracts unit suffix like 'mg' if present.
    """
    s = (raw or "").strip()
    if s == "":
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
        # If dot followed by exactly 3 digits at end -> thousands
        if re.search(r"\.\d{3}$", num_part):
            normalized = num_part.replace(".", "")
        else:
            normalized = num_part
    elif "," in num_part:
        # If comma followed by exactly 3 digits at end -> thousands
        if re.search(r",\d{3}$", num_part):
            normalized = num_part.replace(",", "")
        else:
            # decimal comma
            normalized = num_part.replace(",", ".")
    else:
        normalized = num_part

    try:
        val = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return ParsedNumber(value=None, extracted_unit=unit_part, had_unit_text=had_unit_text, error="Invalid numeric value.")

    return ParsedNumber(value=val, extracted_unit=(unit_part.strip() if unit_part else None), had_unit_text=had_unit_text, error=None)


# --------------------------- Deviation rules ---------------------------

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


# --------------------------- Payload generation ---------------------------

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
    """
    Build one rule entry. Numeric fields are emitted as JSON numbers by using float() conversion
    after quantization; special empty-string sentinel for `value` remains a string exactly '""'.
    """
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
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Returns (payload, warnings).
    """
    warnings: List[str] = []
    rules: List[Dict[str, Any]] = []

    for p in PARAMETERS:
        target = per_param_target.get(p.parametertype_id)
        unit = per_param_unit.get(p.parametertype_id)

        # Empty target => only perfect != rule with value='""'
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
                    value='""',         # critical: literal two quotes as a string
                    linker=None,
                    operator2=None,
                    value2=None,
                )
            )
            continue

        # Target exists: compute bounds based on parameter rules
        # Default: for "other parameters" use deviation percent; for sodium_like depends on unit.
        dev: Optional[Decimal] = None

        # Locked main parameters always use g/100g rules
        if p.group == "locked":
            if p.parametertype_id in (11709, 11710):  # energy kJ/kcal
                dev = deviation_energy(target)
            elif p.parametertype_id == 5239:  # fat total
                dev = deviation_piecewise_10_40(target, low_abs=Decimal("1.5"), high_abs=Decimal("8"))
            elif p.parametertype_id == 5444:  # saturated fat
                dev = deviation_saturated_like(target, threshold=Decimal("4"), low_abs=Decimal("0.8"))
            elif p.parametertype_id in (5244, 5245, 5252, 11423):  # carbs/sugar/fibre/protein
                dev = deviation_piecewise_10_40(target, low_abs=Decimal("2"), high_abs=Decimal("8"))
            elif p.parametertype_id == 11440:  # salt
                dev = deviation_saturated_like(target, threshold=Decimal("1.25"), low_abs=Decimal("0.375"))
            else:
                # Should not happen, but fall back to 20%
                dev = q4(target * Decimal("0.20"))

        elif p.group == "sodium_like":
            # If unit is g/100g, use piecewise; else require deviation%
            if (unit or "").strip() == LOCKED_UNIT:
                if p.parametertype_id == 5299:  # sodium
                    dev = deviation_saturated_like(target, threshold=Decimal("0.5"), low_abs=Decimal("0.15"))
                else:
                    # mono/poly like saturated fat rule
                    dev = deviation_saturated_like(target, threshold=Decimal("4"), low_abs=Decimal("0.8"))
            else:
                perc = per_param_deviation_percent.get(p.parametertype_id)
                if perc is None:
                    warnings.append(
                        f"{p.name}: unit is not '{LOCKED_UNIT}', so deviation% is required. Defaulted to 10%."
                    )
                    perc = Decimal("10")
                dev = deviation_percent(target, perc)

        else:
            # other parameters
            perc = per_param_deviation_percent.get(p.parametertype_id)
            if perc is None:
                warnings.append(f"{p.name}: deviation% not provided. Defaulted to 10%.")
                perc = Decimal("10")
            dev = deviation_percent(target, perc)

        # Compute bounds and clamp
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
    st.set_page_config(page_title="Nutri Rules Generator", layout="wide")
    st.title("Nutri Rules Generator")
    st.caption("Generate Apps Script–compatible Rules JSON for nutrition specs (Rules first).")

    with st.sidebar:
        st.subheader("Global")
        spec_id_raw = st.text_input("spec_id", value="", placeholder="e.g. 1256")
        st.write("")
        st.subheader("Output")
        file_prefix = st.text_input("Filename prefix", value="Rules", help="Used for the download file name.")
        show_preview = st.checkbox("Show computed bounds preview table", value=True)

    # Validate spec_id
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

    st.info(
        "Targets may be blank/null. If blank, a single **perfect** rule is generated using "
        "`operator !=` and `value` set to the special literal string `\"\"`."
    )

    # Per-parameter inputs collected here
    per_param_target: Dict[int, Optional[Decimal]] = {}
    per_param_unit: Dict[int, Optional[str]] = {}
    per_param_dev: Dict[int, Optional[Decimal]] = {}

    # Notes/warnings at input time (e.g., unit text stripped on locked params)
    input_notes: List[str] = []
    parse_errors: List[str] = []

    # Render table-like inputs
    header_cols = st.columns([4, 1.5, 1.5, 1.5])
    header_cols[0].markdown("**Parameter (parametertype_id)**")
    header_cols[1].markdown("**Target**")
    header_cols[2].markdown("**Unit**")
    header_cols[3].markdown("**Deviation %**")

    for p in PARAMETERS:
        cols = st.columns([4, 1.5, 1.5, 1.5])

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

        # Unit field logic
        if p.group == "locked":
            # locked unit
            unit_val = LOCKED_UNIT
            cols[2].write(LOCKED_UNIT)
        elif p.group == "sodium_like":
            # allow unit selection + custom
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

        # Parse target
        parsed = parse_number_with_locale_and_unit(raw_target)

        if parsed.error:
            # If they typed something non-empty but unparsable, record error
            if raw_target.strip() != "":
                parse_errors.append(f"{p.name}: {parsed.error} (input: {raw_target})")
            per_param_target[p.parametertype_id] = None
        else:
            per_param_target[p.parametertype_id] = parsed.value

        # If unit text was present in target and this is locked-unit parameter, show note
        if parsed.had_unit_text and p.group == "locked":
            input_notes.append(f"{p.name}: unit text was removed from target. Note: units must be {LOCKED_UNIT}.")

        # If unit text was present and unit is empty on non-locked params, suggest using extracted unit.
        # (We don't auto-mutate the unit field to avoid confusing reruns.)
        if parsed.had_unit_text and p.group != "locked" and (unit_val is None or str(unit_val).strip() == ""):
            if parsed.extracted_unit:
                input_notes.append(
                    f"{p.name}: detected unit '{parsed.extracted_unit}' in target input. "
                    f"Consider entering it in the Unit field."
                )

        # Save unit
        per_param_unit[p.parametertype_id] = (unit_val.strip() if isinstance(unit_val, str) and unit_val.strip() != "" else unit_val)

        # Deviation% UI: shown only if needed
        needs_dev = False
        if p.parametertype_id in OTHER_PARAM_IDS:
            needs_dev = True
        if p.parametertype_id in SODIUM_LIKE_IDS and (per_param_unit[p.parametertype_id] or "").strip() != LOCKED_UNIT:
            needs_dev = True

        if needs_dev and per_param_target[p.parametertype_id] is not None:
            # Accept 0..50
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

    if input_notes:
        st.warning("\n".join(input_notes))

    if parse_errors:
        st.error("Fix these issues before generating JSON:\n- " + "\n- ".join(parse_errors))

    # Generate
    st.markdown("### Generate")
    can_generate = (spec_id is not None) and (not parse_errors)

    generate_clicked = st.button("Generate Rules JSON", type="primary", disabled=not can_generate)

    if generate_clicked and spec_id is not None and not parse_errors:
        payload, warnings = build_rules_payload(
            spec_id=spec_id,
            per_param_target=per_param_target,
            per_param_unit=per_param_unit,
            per_param_deviation_percent=per_param_dev,
        )

        if warnings:
            st.warning("\n".join(warnings))

        # Preview
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

        # Download
        now = datetime.now()
        fname = f"{file_prefix}_{spec_id}_{now.strftime('%Y%m%d_%H%M')}.json"
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        st.download_button(
            label="Download Rules JSON",
            data=json_bytes,
            file_name=fname,
            mime="application/json",
        )

        st.success(f"Generated {len(payload['rules'])} rules.")

    st.markdown("---")
    st.caption(
        "Notes: UI displays 4dp for consistency; JSON emits numbers. "
        "Empty-target rules use the special `value` string `\"\"` required by LIMS when operator is `!=`."
    )


if __name__ == "__main__":
    main()
