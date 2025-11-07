#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_rules(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError("Input JSON does not have a top-level 'rules' list.")
    return data


def update_spec_id(data: Dict[str, Any], new_spec_id: int) -> Tuple[int, int]:
    """
    Replace data.spec_id in every rules[*].data object.

    Returns
    -------
    (updated_count, total_rules)
    """
    rules: List[Any] = data.get("rules", [])
    updated = 0
    for item in rules:
        if not isinstance(item, dict):
            continue
        d = item.get("data")
        if isinstance(d, dict):
            # set spec_id even if missing (ensures uniformity)
            old = d.get("spec_id")
            d["spec_id"] = int(new_spec_id)
            # count as updated if it existed or we created it
            updated += 1
    return updated, len(rules)


def save_rules(data: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def default_out_path(in_path: Path, new_spec_id: int) -> Path:
    # e.g., Rules_20251105.json -> Rules_20251105_spec789.json
    stem = in_path.stem
    return in_path.with_name(f"{stem}_spec{new_spec_id}.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update spec_id for every rule in a Rules JSON file."
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        required=True,
        help="Path to input Rules JSON (e.g., Rules_20251105.json)",
    )
    parser.add_argument(
        "--spec-id",
        type=int,
        required=True,
        help="New spec_id to set for all rules (integer).",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        default=None,
        help="Output JSON path. If omitted, a suffix like _spec<id>.json is used next to input.",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Overwrite the input file in place (mutually exclusive with --out).",
    )
    args = parser.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")

    if args.inplace and args.out_path is not None:
        raise SystemExit("Use either --inplace or --out, not both.")

    out_path: Path
    if args.inplace:
        out_path = in_path
    elif args.out_path is not None:
        out_path = Path(args.out_path)
    else:
        out_path = default_out_path(in_path, args.spec_id)

    data = load_rules(in_path)
    updated, total = update_spec_id(data, args.spec_id)
    save_rules(data, out_path)

    print(f"Total rules: {total}")
    print(f"Updated spec_id in: {updated} rules")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
