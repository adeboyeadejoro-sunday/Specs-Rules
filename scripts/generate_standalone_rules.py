#!/usr/bin/env python3
"""
generate_standalone_rules.py

Generate rating rules JSON for standalone parameters (no package template).

Supports modes:
  - active     : 4-band active target (perfect, OK low, OK high, not OK)
  - mineral    : same as active but upper OK band ends at 1.45*T
  - limit3     : 3-band limit (perfect <= 0.30*T, OK 0.30*T–T, not OK > T)
  - limit2     : 2-band limit (perfect <= T, not OK > T)
  - qualitative: perfect based on string match, not OK based on numeric threshold
  - dummy      : always-perfect if value != ""

Example
--------
python generate_standalone_rules.py \
  --spec-id 1029 \
  --param 5587 null null dummy \
  --out Dummy_Rules_1029.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


Mode = Literal[
    "active",
    "mineral",
    "limit3",
    "limit2",
    "qualitative",
    "dummy",
]


@dataclass(frozen=True)
class ParamSpec:
    parametertype_id: int
    target: Optional[float]
    unit: Optional[str]
    mode: Mode


# ---------------------------------
# Helpers
# ---------------------------------

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


# ---------------------------------
# Active band calculation
# ---------------------------------

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


# ---------------------------------
# Mineral band calculation
# ---------------------------------

def compute_mineral_bands(target: float) -> ActiveBands:
    return ActiveBands(
        low_ok=r2(0.80 * target),
        low_perfect=r2(0.90 * target),
        high_perfect=r2(1.25 * target),
        high_ok2=r2(1.45 * target),  # mineral-specific change
    )


# ---------------------------------
# Rule builders
# ---------------------------------

def build_active_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    if t == 0:
        perfect = make_rule(base_data(
            parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
            ddf_type="perfect", color="green",
            operator="<=", value=0.0
        ))
        not_ok = make_rule(base_data(
            parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
            ddf_type="not OK", color="red",
            operator=">", value=0.0
        ))
        return [perfect, not_ok]

    b = compute_active_bands(t)

    perfect = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="perfect", color="green",
        operator=">=", operator2="<=", linker="AND",
        value=b.low_perfect, value2=b.high_perfect
    ))

    ok_low = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="OK", color="orange",
        operator=">=", operator2="<", linker="AND",
        value=b.low_ok, value2=b.low_perfect
    ))

    ok_high = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="OK", color="orange",
        operator=">", operator2="<=", linker="AND",
        value=b.high_perfect, value2=b.high_ok2
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="not OK", color="red",
        operator="<", operator2=">", linker="OR",
        value=b.low_ok, value2=b.high_ok2
    ))

    return [perfect, ok_low, ok_high, not_ok]


def build_mineral_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    if t == 0:
        perfect = make_rule(base_data(
            parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
            ddf_type="perfect", color="green",
            operator="<=", value=0.0
        ))
        not_ok = make_rule(base_data(
            parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
            ddf_type="not OK", color="red",
            operator=">", value=0.0
        ))
        return [perfect, not_ok]

    b = compute_mineral_bands(t)

    perfect = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="perfect", color="green",
        operator=">=", operator2="<=", linker="AND",
        value=b.low_perfect, value2=b.high_perfect
    ))

    ok_low = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="OK", color="orange",
        operator=">=", operator2="<", linker="AND",
        value=b.low_ok, value2=b.low_perfect
    ))

    ok_high = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="OK", color="orange",
        operator=">", operator2="<=", linker="AND",
        value=b.high_perfect, value2=b.high_ok2
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="not OK", color="red",
        operator="<", operator2=">", linker="OR",
        value=b.low_ok, value2=b.high_ok2
    ))

    return [perfect, ok_low, ok_high, not_ok]


# ---------------------------------
# Other builders
# ---------------------------------

def build_limit3_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    if t == 0:
        perfect = make_rule(base_data(
            parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
            ddf_type="perfect", color="green",
            operator="<=", value=0.0
        ))
        not_ok = make_rule(base_data(
            parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
            ddf_type="not OK", color="red",
            operator=">", value=0.0
        ))
        return [perfect, not_ok]

    threshold_perfect = r2(0.30 * t)

    perfect = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="perfect", color="green",
        operator="<=", value=threshold_perfect
    ))

    ok = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="OK", color="orange",
        operator=">=", operator2="<=", linker="AND",
        value=threshold_perfect, value2=r2(t)
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="not OK", color="red",
        operator=">", value=r2(t)
    ))

    return [perfect, ok, not_ok]


def build_limit2_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    perfect = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="perfect", color="green",
        operator="<=", value=r2(t)
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="not OK", color="red",
        operator=">", value=r2(t)
    ))

    return [perfect, not_ok]


def build_qualitative_rules(ps: ParamSpec, spec_id: int, qual_en: str, qual_de: str) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id
    t = float(ps.target)
    unit = ps.unit

    perfect = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="perfect", color="green",
        operator="=", operator2="=", linker="OR",
        value=qual_en, value2=qual_de
    ))

    not_ok = make_rule(base_data(
        parametertype_id=pid, spec_id=spec_id, unit=unit, target=t,
        ddf_type="not OK", color="red",
        operator=">", value=r2(t)
    ))

    return [perfect, not_ok]


def build_dummy_rules(ps: ParamSpec, spec_id: int) -> List[Dict[str, Any]]:
    pid = ps.parametertype_id

    rule = make_rule(base_data(
        parametertype_id=pid,
        spec_id=spec_id,
        unit=None,
        target=None,
        ddf_type="perfect",
        color="green",
        operator="!=",
        value='""',
    ))

    return [rule]


# ---------------------------------
# CLI parsing
# ---------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate rules JSON for standalone parameters."
    )

    parser.add_argument("--spec-id", type=int, required=True)

    parser.add_argument(
        "--param",
        dest="params",
        nargs=4,
        action="append",
        required=True,
        metavar=("PARAM_ID", "TARGET", "UNIT", "MODE"),
    )

    parser.add_argument(
        "--qual",
        dest="qual",
        nargs=2,
        default=None,
        help="Qualitative texts EN DE",
    )

    parser.add_argument(
        "--out",
        dest="out_path",
        required=True,
    )

    return parser.parse_args()


def parse_param(raw: List[str]) -> ParamSpec:
    pid_str, target_str, unit_str, mode_str = raw

    try:
        pid = int(pid_str)
    except ValueError as e:
        raise ValueError(f"Invalid parametertype_id '{pid_str}'. Must be int.") from e

    mode = mode_str.strip().lower()
    if mode not in ("active", "mineral", "limit3", "limit2", "qualitative", "dummy"):
        raise ValueError(f"Invalid mode '{mode_str}'.")

    # target
    if target_str.lower() == "null":
        target = None
    else:
        t_norm = target_str.replace(",", ".")
        try:
            target = float(t_norm)
        except ValueError as e:
            raise ValueError(f"Invalid target '{target_str}'.") from e

    unit = None if unit_str.lower() == "null" else unit_str

    return ParamSpec(
        parametertype_id=pid,
        target=target,
        unit=unit,
        mode=mode,  # type: ignore
    )


# ---------------------------------
# main
# ---------------------------------

def main() -> None:
    args = parse_args()
    spec_id: int = args.spec_id
    out_path: Path = Path(args.out_path)

    param_specs: List[ParamSpec] = [parse_param(p) for p in args.params]

    # qualitative check
    any_qualitative = any(ps.mode == "qualitative" for ps in param_specs)
    if any_qualitative and args.qual is None:
        raise SystemExit("Qualitative mode requires --qual EN DE")

    qual_en, qual_de = args.qual if args.qual else ("", "")

    all_rules: List[Dict[str, Any]] = []

    for ps in param_specs:
        if ps.mode == "active":
            if ps.target is None:
                raise SystemExit("Active requires numeric target.")
            rules = build_active_rules(ps, spec_id)

        elif ps.mode == "mineral":
            if ps.target is None:
                raise SystemExit("Mineral requires numeric target.")
            rules = build_mineral_rules(ps, spec_id)

        elif ps.mode == "limit3":
            if ps.target is None:
                raise SystemExit("Limit3 requires numeric target.")
            rules = build_limit3_rules(ps, spec_id)

        elif ps.mode == "limit2":
            if ps.target is None:
                raise SystemExit("Limit2 requires numeric target.")
            rules = build_limit2_rules(ps, spec_id)

        elif ps.mode == "qualitative":
            if ps.target is None:
                raise SystemExit("Qualitative requires numeric target.")
            rules = build_qualitative_rules(ps, spec_id, qual_en, qual_de)

        elif ps.mode == "dummy":
            rules = build_dummy_rules(ps, spec_id)

        else:
            raise ValueError(f"Unsupported mode: {ps.mode}")

        all_rules.extend(rules)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"rules": all_rules}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(all_rules)} rules to {out_path}")

    # summary
    for ps in param_specs:
        if ps.mode == "active":
            n = 2 if ps.target == 0 else 4
        elif ps.mode == "mineral":
            n = 2 if ps.target == 0 else 4
        elif ps.mode == "limit3":
            n = 2 if ps.target == 0 else 3
        elif ps.mode == "limit2":
            n = 2
        elif ps.mode == "qualitative":
            n = 2
        elif ps.mode == "dummy":
            n = 1
        else:
            n = 0

        print(f"  param {ps.parametertype_id} ({ps.mode}) -> {n} rules")


if __name__ == "__main__":
    main()
