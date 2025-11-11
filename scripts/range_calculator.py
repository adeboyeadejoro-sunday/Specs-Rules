#!/usr/bin/env python3
"""
range_calculator.py

Usage:
  python range_calculator.py --target 12 --type active
  python range_calculator.py --target 12 --type limit

Behavior:
- type=active:
    perfect_range  = 0.90*target  to 1.25*target
    okay_range     = 0.80*target  to 0.90*target
    okay_range_2   = 1.25*target  to 1.50*target
    not_okay_range = <0.80*target OR >1.50*target
- type=limit:
    perfect_range  = <= 0.30*target
    okay_range     = 0.30*target to target
    not_okay_range = > target
- Special case: target == 0
    perfect_range: 0
    not_okay_range: > 0
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Literal


TypeMode = Literal["active", "limit"]


@dataclass(frozen=True)
class ActiveBands:
    low_ok: float        # 0.80 * target
    low_perfect: float   # 0.90 * target
    high_perfect: float  # 1.25 * target
    high_ok2: float      # 1.50 * target


def fmt(value: float) -> str:
    """Format a float to two decimal places."""
    return f"{value:.2f}"


def compute_active_bands(target: float) -> ActiveBands:
    """Compute the fixed percentage bands for type=active."""
    return ActiveBands(
        low_ok=0.80 * target,
        low_perfect=0.90 * target,
        high_perfect=1.25 * target,
        high_ok2=1.50 * target,
    )


def print_active_ranges(target: float) -> None:
    """Print the ranges for type=active with two-decimal formatting."""
    bands: ActiveBands = compute_active_bands(target)

    print(f"perfect_range: {fmt(bands.low_perfect)} - {fmt(bands.high_perfect)}")
    print(f"okay_range: {fmt(bands.low_ok)} - {fmt(bands.low_perfect)}")
    print(f"okay_range_2: {fmt(bands.high_perfect)} - {fmt(bands.high_ok2)}")
    print(f"not_okay_range: <{fmt(bands.low_ok)} OR >{fmt(bands.high_ok2)}")


def print_limit_ranges(target: float) -> None:
    """Print the ranges for type=limit with two-decimal formatting."""
    threshold_perfect: float = 0.30 * target

    print(f"perfect_range: <= {fmt(threshold_perfect)}")
    print(f"okay_range: {fmt(threshold_perfect)} - {fmt(target)}")
    print(f"not_okay_range: > {fmt(target)}")


def print_zero_target_special_case() -> None:
    """Special handling when target == 0."""
    print("perfect_range: 0.00")
    print("not_okay_range: > 0.00")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate quality ranges around a target using fixed rules."
    )
    # --target: numeric float. Required.
    parser.add_argument(
        "--target",
        type=float,
        required=True,
        help="Numeric target value. Example: --target 12",
    )
    # --type: either 'active' or 'limit'. Required.
    parser.add_argument(
        "--type",
        choices=["active", "limit"],
        required=True,
        help="Range rule type. One of: active, limit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target: float = args.target
    mode: TypeMode = args.type  # type: ignore[assignment]

    # Special case for target == 0
    if target == 0:
        print_zero_target_special_case()
        return

    if mode == "active":
        print_active_ranges(target)
    elif mode == "limit":
        print_limit_ranges(target)
    else:
        # argparse choices already guards this, but this keeps mypy happy.
        raise ValueError("Unsupported --type. Use 'active' or 'limit'.")


if __name__ == "__main__":
    main()
