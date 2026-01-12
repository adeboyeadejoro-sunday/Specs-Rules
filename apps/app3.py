#!/usr/bin/env python3
"""
app.py — Exim Int Lab Rules Generator (Streamlit)

Supports mixed per-parameter modes in a single run:
- Lower bound only: normal (single threshold)
- Dummy mode: perfect != "" (LIMS expects literal '""' string)
- Lower / upper bound: density only; lower + upper

Rules are generated Apps Script / LIMS compatible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional

import streamlit as st


# ----------------------------- Constants -----------------------------

MODE_LOWER_ONLY: str = "lower"
MODE_DUMMY: str = "dummy"
MODE_LOWER_UPPER: str = "lower_upper"

MODE_LABELS: Dict[str, str] = {
    MODE_LOWER_ONLY: "Lower bound only",
    MODE_DUMMY: "Dummy mode",
    MODE_LOWER_UPPER: "Lower / upper bound",
}

Q4 = Decimal("0.0001")


def q4(x: Decimal) -> Decimal:
    return x.quantize(Q4, rounding=ROUND_HALF_UP)


# ----------------------------- Parameters -----------------------------

@dataclass(frozen=True)
class Param:
    id: int
    name: str
    kind: str  # density | moisture | mesh
    default_unit: Optional[str]


PARAMS: List[Param] = [
    Param(11194, "Bulk Density", "density", "g/cm3"),
    Param(11196, "Moisture content analysis", "moisture", "%"),
    Param(11974, "Tapped Density", "density", "g/cm3"),
    Param(11975, "Mesh Size", "mesh", "%"),
    Param(12029, "Mesh Size 20", "mesh", "%"),
    Param(12030, "Mesh Size 40", "mesh", "%"),
    Param(12031, "Mesh Size 60", "mesh", "%"),
    Param(12032, "Mesh Size 80", "mesh", "%"),
    Param(12033, "Mesh Size 100", "mesh", "%"),
]

DENSITY_IDS = {11194, 11974}


# ----------------------------- Payload helpers -----------------------------

def rule(
    *,
    spec_id: int,
    param_id: int,
    ddf_type: str,
    color: str,
    operator: str,
    value: Any,
    linker: Optional[str],
    operator2: Optional[str],
    value2: Optional[Any],
    target: Optional[Decimal],
    unit: Optional[str],
) -> Dict[str, Any]:
    return {
        "action": "create",
        "data": {
            "color": color,
            "column": 0,
            "DDF_target_value": float(q4(target)) if target is not None else None,
            "DDF_type": ddf_type,
            "DDF_unit": unit if unit else None,
            "inverse": 0,
            "linker": linker,
            "operator": operator,
            "operator2": operator2,
            "parametertype_id": param_id,
            "regex_filter": None,
            "show": 1,
            "spec_id": spec_id,
            "text": None,
            "translations": None,
            "value": value,
            "value2": value2,
        },
    }


# ----------------------------- Numeric parsing -----------------------------

def parse_decimal(s: str) -> Optional[Decimal]:
    s = (s or "").strip()
    if s == "" or s.lower() == "null":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# ----------------------------- Streamlit UI -----------------------------

def main() -> None:
    st.set_page_config(page_title="Exim Int Lab Rules Generator", layout="wide")
    st.title("Exim Int Lab — Rules Generator")

    with st.sidebar:
        st.subheader("Global")
        spec_raw: str = st.text_input("spec_id", placeholder="e.g. 4906")
        fname_prefix: str = st.text_input("Filename prefix", value="Rules_Exim")
        show_preview: bool = st.checkbox("Show preview", value=True)

    # spec_id validation
    spec_id: Optional[int] = None
    if spec_raw.strip():
        try:
            spec_id = int(float(spec_raw.strip()))
        except Exception:
            st.error("spec_id must be an integer")

    st.markdown("### Parameters")

    headers = st.columns([3, 1.5, 1.3, 1.3, 1.2])
    headers[0].markdown("**Parameter**")
    headers[1].markdown("**Mode**")
    headers[2].markdown("**Target / Lower**")
    headers[3].markdown("**Upper**")
    headers[4].markdown("**Unit**")

    # collected inputs
    modes: Dict[int, str] = {}
    targets: Dict[int, Optional[Decimal]] = {}
    uppers: Dict[int, Optional[Decimal]] = {}
    units: Dict[int, Optional[str]] = {}

    warnings: List[str] = []

    for p in PARAMS:
        cols = st.columns([3, 1.5, 1.3, 1.3, 1.2])

        cols[0].write(f"{p.name}\n`{p.id}`")

        # Mode selector:
        # - density params: can choose among all 3
        # - others: only Lower bound only or Dummy mode (no Upper bound mode)
        if p.id in DENSITY_IDS:
            mode_options = [MODE_LOWER_ONLY, MODE_DUMMY, MODE_LOWER_UPPER]
        else:
            mode_options = [MODE_LOWER_ONLY, MODE_DUMMY]

        mode = cols[1].selectbox(
            "",
            options=mode_options,
            format_func=lambda k: MODE_LABELS[k],
            key=f"mode_{p.id}",
        )
        modes[p.id] = mode

        # numeric fields
        target_val: Optional[Decimal] = None
        upper_val: Optional[Decimal] = None

        if mode == MODE_DUMMY:
            cols[2].write("—")
            cols[3].write("—")
        elif mode == MODE_LOWER_ONLY:
            t_raw = cols[2].text_input("", key=f"t_{p.id}")
            target_val = parse_decimal(t_raw)
            cols[3].write("—")
        elif mode == MODE_LOWER_UPPER:
            t_raw = cols[2].text_input("", key=f"l_{p.id}")
            u_raw = cols[3].text_input("", key=f"u_{p.id}")
            target_val = parse_decimal(t_raw)
            upper_val = parse_decimal(u_raw)
        else:
            raise RuntimeError(f"Unknown mode: {mode}")

        # clamp negatives (and warn)
        if target_val is not None and target_val < 0:
            target_val = Decimal("0")
            warnings.append(f"{p.name}: lower/target was negative and was clamped to 0")

        if upper_val is not None and upper_val < 0:
            upper_val = Decimal("0")
            warnings.append(f"{p.name}: upper bound was negative and was clamped to 0")

        # auto-swap for lower/upper mode (and warn)
        if mode == MODE_LOWER_UPPER and target_val is not None and upper_val is not None:
            if target_val >= upper_val:
                target_val, upper_val = upper_val, target_val
                warnings.append(f"{p.name}: lower ≥ upper — values were auto-swapped")

        targets[p.id] = target_val
        uppers[p.id] = upper_val

        # unit (editable)
        if p.default_unit is not None:
            unit_val = cols[4].text_input("", value=p.default_unit, key=f"unit_{p.id}")
        else:
            unit_val = cols[4].text_input("", key=f"unit_{p.id}")

        units[p.id] = unit_val.strip() if unit_val.strip() else None

    if warnings:
        st.warning("\n".join(warnings))

    st.markdown("### Generate")

    if st.button("Generate Rules JSON", type="primary", disabled=spec_id is None):
        rules: List[Dict[str, Any]] = []

        for p in PARAMS:
            mode = modes[p.id]
            unit = units[p.id]
            t = targets[p.id]
            u = uppers[p.id]

            # ---------------- Dummy mode ----------------
            if mode == MODE_DUMMY:
                rules.append(
                    rule(
                        spec_id=spec_id,
                        param_id=p.id,
                        ddf_type="perfect",
                        color="green",
                        operator="!=",
                        value='""',  # CRITICAL: LIMS expects literal "" string here
                        linker=None,
                        operator2=None,
                        value2=None,
                        target=None,
                        unit=unit,
                    )
                )
                continue

            # ---------------- Lower bound only ----------------
            if mode == MODE_LOWER_ONLY:
                if t is None:
                    # If no threshold provided, skip generating rules for this param
                    continue

                if p.kind == "moisture":
                    # reversed logic
                    rules.append(
                        rule(
                            spec_id=spec_id,
                            param_id=p.id,
                            ddf_type="perfect",
                            color="green",
                            operator="<=",
                            value=float(q4(t)),
                            linker=None,
                            operator2=None,
                            value2=None,
                            target=t,
                            unit=unit,
                        )
                    )
                    rules.append(
                        rule(
                            spec_id=spec_id,
                            param_id=p.id,
                            ddf_type="not OK",
                            color="red",
                            operator=">=",
                            value=float(q4(t)),
                            linker=None,
                            operator2=None,
                            value2=None,
                            target=t,
                            unit=unit,
                        )
                    )
                else:
                    rules.append(
                        rule(
                            spec_id=spec_id,
                            param_id=p.id,
                            ddf_type="perfect",
                            color="green",
                            operator=">=",
                            value=float(q4(t)),
                            linker=None,
                            operator2=None,
                            value2=None,
                            target=t,
                            unit=unit,
                        )
                    )
                    rules.append(
                        rule(
                            spec_id=spec_id,
                            param_id=p.id,
                            ddf_type="not OK",
                            color="red",
                            operator="<=",
                            value=float(q4(t)),
                            linker=None,
                            operator2=None,
                            value2=None,
                            target=t,
                            unit=unit,
                        )
                    )
                continue

            # ---------------- Lower / upper bound (density only) ----------------
            if mode == MODE_LOWER_UPPER:
                if p.id not in DENSITY_IDS:
                    # Shouldn't happen due to UI options, but keep safe
                    continue
                if t is None or u is None:
                    continue

                rules.append(
                    rule(
                        spec_id=spec_id,
                        param_id=p.id,
                        ddf_type="perfect",
                        color="green",
                        operator=">=",
                        value=float(q4(t)),
                        linker="AND",
                        operator2="<=",
                        value2=float(q4(u)),
                        target=t,
                        unit=unit,
                    )
                )
                rules.append(
                    rule(
                        spec_id=spec_id,
                        param_id=p.id,
                        ddf_type="not OK",
                        color="red",
                        operator="<=",
                        value=float(q4(t)),
                        linker="OR",
                        operator2=">=",
                        value2=float(q4(u)),
                        target=t,
                        unit=unit,
                    )
                )
                continue

            raise RuntimeError(f"Unknown mode: {mode}")

        payload: Dict[str, Any] = {"rules": rules}

        if show_preview:
            st.markdown("### Preview")
            st.dataframe(
                [
                    {
                        "param_id": r["data"]["parametertype_id"],
                        "type": r["data"]["DDF_type"],
                        "operator": r["data"]["operator"],
                        "value": r["data"]["value"],
                        "linker": r["data"]["linker"],
                        "operator2": r["data"]["operator2"],
                        "value2": r["data"]["value2"],
                        "unit": r["data"]["DDF_unit"],
                    }
                    for r in rules
                ],
                use_container_width=True,
                height=420,
            )

        fname = f"{fname_prefix}_{spec_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        st.download_button(
            "Download Rules JSON",
            data=json.dumps(payload, indent=2).encode("utf-8"),
            file_name=fname,
            mime="application/json",
        )

        st.success(f"Generated {len(rules)} rules.")


if __name__ == "__main__":
    main()
