#!/usr/bin/env python3
"""
generate_standalone_rules.py

Generate rating rules JSON for standalone parameters (no package template).

Supports modes:
  - active   : 4-band active target (perfect, OK low, OK high, not OK)
  - limit3   : 3-band limit (perfect <= 0.30*T, OK 0.30*T–T, not OK > T)
  - limit2   : 2-band limit (perfect <= T, not OK > T)
  - qualitative : perfect based on string match, not OK based on numeric threshold

Examples
--------
# Active (Spermidine-like)
python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5253 3 mg active \
  --out Spermidine_Rules_1083.json

# Multiple params, mixed modes
python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5253 3 mg active \
  --param 6002 0.01 "mg/kg" limit2 \
  --param 6010 1000 "CFU/g" limit3 \
  --out Standalone_Rules_1083.json

# Qualitative perfect + numeric not OK
python generate_standalone_rules.py \
  --spec-id 1083 \
  --param 5369 0 "mg/kg" qualitative \
  --qual "not detectable" "nicht nachw." \
  --out Qual_Rules_1083.json

Notes
-----
- All numeric ranges are rounded to 2 decimals and stored as numbers.
- DDF_type is forced to exactly: "perfect", "OK", "not OK".
- Colors are fixed: perfect->green, OK->orange, not OK->red.
- Special case target == 0 for numeric modes:
    perfect_range: 0
    not_okay_range: >0
    (no OK rules)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple


Mode = Literal["active", "limit3", "limit2", "qualitative"]


@dataclass(frozen=True)
class ParamSpec:
    """One standalone parameter request from CLI."""
    parametertype_id: int
    target: float
    unit: str
    mode: Mode


# ---------------------------
# Helpers / constants
# ---------------------------

def r2(x: float) -> float:
    """Round to two decimals."""
    return round(x, 2)


def base_data(
    *,
    parametertype_id: int,
    spec_id: int,
    unit: str,
    target: float,
    ddf_type: Literal["perfect", "OK", "not OK"],
    color: Literal["green", "orange", "red"],
    operator: str,
    value: Any,
    operator2: Optional[str] = None,
    value2: Any = None,
    linker: Optional[Literal["AND", "OR"]] = None,
) -> Dict[str, Any]:
    """
    Build the standard 'data' object with boilerplate fields.

    Parameters
    ----------
    parametertype_id : int
        LIMS parameter type ID.
    spec_id : int
        Spec ID to apply to every rule.
    unit : str
        DDF_unit for the rule.
    target : float
        DDF_target_value for the rule (numeric).
    ddf_type : {"perfect","OK","not OK"}
        Rating label.
    color : {"green","orange","red"}
        UI color mapping.
    operator / operator2 : str | None
        Primary / secondary comparison operator.
    value / value2 : Any
        Primary and secondary comparison values (numeric or string).
    linker : {"AND","OR"} | None
        How operator/operator2 are combined.
    """
    return {
        "color": color,
        "column": 0,
        "DDF_target_value": target,
        "DDF_type": ddf_type,     # already normalized by construction
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
    """Wrap a data-object into a full rule."""
    return {"action": "create", "data": data}


# ---------------------------
# Band computations
# ---------------------------

@dataclass(frozen=True)
class ActiveBands:
    low_ok: float
    low_perfect: float
    high_perfect: float
    high_ok2: float


def compute_active_bands(target: float) -> ActiveBands:
    """Compute active bands (fixed percentages)."""
    return ActiveBands(
        low_ok=r2(0.80 * target),
        low_perfect=r2(0.90 * target),
        high_perfect=r2(1.25 * target),
        high_ok2=r2(1.50 * target),
    )


# ---------------------------
# Rule builders per mode
# ---------------------------

def build_active_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    """
    Active mode => 4 rules unless target == 0 (special case => 2 rules).
    """
    pid = ps.parametertype_id
    t = ps.target
    unit = ps.unit

    if t == 0:
        # Special case: perfect == 0, not OK > 0
        perfect = make_rule(base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator="<=",
            value=0.0
        ))
        not_ok = make_rule(base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator=">",
            value=0.0
        ))
        return [perfect, not_ok]

    b = compute_active_bands(t)

    perfect = make_rule(base_data(
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
    ))

    ok_low = make_rule(base_data(
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
    ))

    ok_high = make_rule(base_data(
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
    ))

    not_ok = make_rule(base_data(
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
    ))

    return [perfect, ok_low, ok_high, not_ok]


def build_limit3_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    """
    Limit3 mode => 3 rules unless target == 0 (special case => 2 rules).
    """
    pid = ps.parametertype_id
    t = ps.target
    unit = ps.unit

    if t == 0:
        perfect = make_rule(base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="perfect",
            color="green",
            operator="<=",
            value=0.0
        ))
        not_ok = make_rule(base_data(
            parametertype_id=pid,
            spec_id=spec_id,
            unit=unit,
            target=t,
            ddf_type="not OK",
            color="red",
            operator=">",
            value=0.0
        ))
        return [perfect, not_ok]

    threshold_perfect = r2(0.30 * t)

    perfect = make_rule(base_data(
        parametertype_id=pid,
        spec_id=spec_id,
        unit=unit,
        target=t,
        ddf_type="perfect",
        color="green",
        operator="<=",
        value=threshold_perfect,
    ))

    ok = make_rule(base_data(
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
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid,
        spec_id=spec_id,
        unit=unit,
        target=t,
        ddf_type="not OK",
        color="red",
        operator=">",
        value=r2(t),
    ))

    return [perfect, ok, not_ok]


def build_limit2_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    """
    Limit2 mode => 2 rules unless target == 0 (special case also => 2 rules).
    """
    pid = ps.parametertype_id
    t = ps.target
    unit = ps.unit

    # For t==0, this still matches special-case requirement.
    perfect = make_rule(base_data(
        parametertype_id=pid,
        spec_id=spec_id,
        unit=unit,
        target=t,
        ddf_type="perfect",
        color="green",
        operator="<=",
        value=r2(t),
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid,
        spec_id=spec_id,
        unit=unit,
        target=t,
        ddf_type="not OK",
        color="red",
        operator=">",
        value=r2(t),
    ))

    return [perfect, not_ok]


def build_qualitative_rules(
    ps: ParamSpec,
    spec_id: int,
    qual_en: str,
    qual_de: str,
) -> List[Dict[str, Any]]:
    """
    Qualitative mode => 2 rules:
      1) perfect by string match (EN/DE)
      2) not OK by numeric threshold (> target)
    """
    pid = ps.parametertype_id
    t = ps.target
    unit = ps.unit

    perfect = make_rule(base_data(
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
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid,
        spec_id=spec_id,
        unit=unit,
        target=t,
        ddf_type="not OK",
        color="red",
        operator=">",
        value=r2(t),
    ))

    return [perfect, not_ok]


# ---------------------------
# CLI parsing / main
# ---------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate rules JSON for standalone parameters."
    )
    parser.add_argument(
        "--spec-id",
        type=int,
        required=True,
        help="Spec ID to apply to all rules."
    )
    parser.add_argument(
        "--param",
        dest="params",
        nargs=4,
        action="append",
        required=True,
        metavar=("PARAM_ID", "TARGET", "UNIT", "MODE"),
        help=(
            "Standalone parameter spec. Repeatable. "
            "Format: --param <parametertype_id> <target> <unit> <mode>\n"
            "Modes: active | limit3 | limit2 | qualitative"
        )
    )
    parser.add_argument(
        "--qual",
        dest="qual",
        nargs=2,
        default=None,
        metavar=("EN_TEXT", "DE_TEXT"),
        help=(
            "Qualitative perfect match texts (EN and DE). "
            "Required if any parameter uses mode=qualitative."
        )
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        required=True,
        help="Output JSON path."
    )
    return parser.parse_args()


def parse_param(raw: List[str]) -> ParamSpec:
    """
    Parse one --param group into ParamSpec.
    raw = [id, target, unit, mode]
    """
    pid_str, target_str, unit, mode_str = raw

    try:
        pid = int(pid_str)
    except ValueError as e:
        raise ValueError(f"Invalid parametertype_id '{pid_str}'. Must be int.") from e

    # Normalize German decimal comma if present
    target_norm = target_str.replace(",", ".")
    try:
        target = float(target_norm)
    except ValueError as e:
        raise ValueError(f"Invalid target '{target_str}'. Must be numeric.") from e

    mode = mode_str.strip().lower()
    if mode not in ("active", "limit3", "limit2", "qualitative"):
        raise ValueError(
            f"Invalid mode '{mode_str}'. "
            "Must be one of: active, limit3, limit2, qualitative."
        )

    return ParamSpec(
        parametertype_id=pid,
        target=target,
        unit=unit,
        mode=mode,  # type: ignore[assignment]
    )


def main() -> None:
    args = parse_args()
    spec_id: int = args.spec_id
    out_path: Path = Path(args.out_path)

    param_specs: List[ParamSpec] = [parse_param(p) for p in args.params]

    # Check qualitative requirements
    any_qualitative = any(ps.mode == "qualitative" for ps in param_specs)
    if any_qualitative:
        if args.qual is None:
            raise SystemExit(
                "At least one parameter uses mode=qualitative, "
                "but --qual was not provided."
            )
        qual_en, qual_de = args.qual
    else:
        qual_en, qual_de = "", ""

    all_rules: List[Dict[str, Any]] = []

    for ps in param_specs:
        if ps.mode == "active":
            rules = build_active_rules(ps, spec_id)
        elif ps.mode == "limit3":
            rules = build_limit3_rules(ps, spec_id)
        elif ps.mode == "limit2":
            rules = build_limit2_rules(ps, spec_id)
        elif ps.mode == "qualitative":
            rules = build_qualitative_rules(ps, spec_id, qual_en, qual_de)
        else:
            # unreachable given validation
            raise ValueError(f"Unsupported mode: {ps.mode}")

        all_rules.extend(rules)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"rules": all_rules}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(all_rules)} rules to {out_path}")
    # Optional per-param summary
    for ps in param_specs:
        if ps.mode == "active":
            n = 2 if ps.target == 0 else 4
        elif ps.mode == "limit3":
            n = 2 if ps.target == 0 else 3
        else:
            n = 2
        print(f"  param {ps.parametertype_id} ({ps.mode}) -> {n} rules")


if __name__ == "__main__":
    main()
