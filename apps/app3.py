#!/usr/bin/env python3
"""
app.py — Exim Int Lab Rules Generator (Streamlit)

Supports mixed per-parameter modes in a single run:
- Mode A: normal (single threshold)
- Mode B: dummy (perfect != "")
- Mode C: upper bound (density only; lower + upper)

Rules are generated Apps Script / LIMS compatible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# ----------------------------- Constants -----------------------------

Q4 = Decimal("0.0001")


def q4(x: Decimal) -> Decimal:
    return x.quantize(Q4, rounding=ROUND_HALF_UP)


def clamp0(x: Decimal) -> Decimal:
    return x if x >= Decimal("0") else Decimal("0")


# ----------------------------- Parameters -----------------------------

@dataclass(frozen=True)
class Param:
    id: int
    name: str
    kind: str      # density | moisture | mesh
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
        spec_raw = st.text_input("spec_id", placeholder="e.g. 4906")
        fname_prefix = st.text_input("Filename prefix", value="Rules_Exim")
        show_preview = st.checkbox("Show preview", value=True)

    # spec_id validation
    spec_id: Optional[int] = None
    if spec_raw.strip():
        try:
            spec_id = int(float(spec_raw.strip()))
        except Exception:
            st.error("spec_id must be an integer")

    st.markdown("### Parameters")

    headers = st.columns([3, 1.3, 1.2, 1.2, 1.2])
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
        cols = st.columns([3, 1.3, 1.2, 1.2, 1.2])

        cols[0].write(f"{p.name}\n`{p.id}`")

        mode = cols[1].selectbox(
            "",
            ["Mode A", "Mode B", "Mode C"],
            index=0 if p.id not in DENSITY_IDS else 0,
            disabled=(p.id not in DENSITY_IDS),
            key=f"mode_{p.id}",
        )
        modes[p.id] = mode

        # numeric fields
        target_val: Optional[Decimal] = None
        upper_val: Optional[Decimal] = None

        if mode == "Mode B":
            cols[2].write("—")
            cols[3].write("—")
        elif mode == "Mode A":
            t_raw = cols[2].text_input("", key=f"t_{p.id}")
            target_val = parse_decimal(t_raw)
            cols[3].write("—")
        else:  # Mode C
            t_raw = cols[2].text_input("", key=f"l_{p.id}")
            u_raw = cols[3].text_input("", key=f"u_{p.id}")
            target_val = parse_decimal(t_raw)
            upper_val = parse_decimal(u_raw)

        # clamp negatives
        if target_val is not None and target_val < 0:
            target_val = Decimal("0")
            warnings.append(f"{p.name}: lower/target clamped to 0")

        if upper_val is not None and upper_val < 0:
            upper_val = Decimal("0")
            warnings.append(f"{p.name}: upper bound clamped to 0")

        # auto-swap
        if mode == "Mode C" and target_val is not None and upper_val is not None:
            if target_val >= upper_val:
                target_val, upper_val = upper_val, target_val
                warnings.append(f"{p.name}: lower ≥ upper — values auto-swapped")

        targets[p.id] = target_val
        uppers[p.id] = upper_val

        # unit
        if p.default_unit:
            unit_val = cols[4].text_input(
                "",
                value=p.default_unit,
                key=f"unit_{p.id}",
            )
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

            # ---------------- Mode B ----------------
            if mode == "Mode B":
                rules.append(
                    rule(
                        spec_id=spec_id,
                        param_id=p.id,
                        ddf_type="perfect",
                        color="green",
                        operator="!=",
                        value='""',   # CRITICAL
                        linker=None,
                        operator2=None,
                        value2=None,
                        target=None,
                        unit=unit,
                    )
                )
                continue

            # ---------------- Mode A ----------------
            if mode == "Mode A":
                if t is None:
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

            # ---------------- Mode C (density only) ----------------
            if mode == "Mode C":
                if p.id not in DENSITY_IDS or t is None or u is None:
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

        payload = {"rules": rules}

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
