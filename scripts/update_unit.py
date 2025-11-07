#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def load_rules(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError("Input JSON does not have a top-level 'rules' list.")
    return data


def parse_param_ids(values: Optional[Iterable[str]]) -> Optional[Set[int]]:
    if not values:
        return None
    out: Set[int] = set()
    for v in values:
        v = v.strip()
        if v:
            out.add(int(v))
    return out if out else None


def update_unit(
    data: Dict[str, Any],
    new_unit: Optional[str],
    *,
    only_missing: bool = False,
    restrict_param_ids: Optional[Set[int]] = None,
) -> Tuple[int, int]:
    """
    Update DDF_unit in rules[*].data.

    Parameters
    ----------
    data : Dict[str, Any]
        Parsed JSON with top-level 'rules' list.
    new_unit : Optional[str]
        String to set as unit, or None to clear to null.
    only_missing : bool
        If True, only update rules where DDF_unit is currently None or empty string.
    restrict_param_ids : Optional[Set[int]]
        If provided, only update rules whose data.parametertype_id is in this set.

    Returns
    -------
    updated_count, total_rules
    """
    rules: List[Any] = data.get("rules", [])
    updated = 0
    for item in rules:
        if not isinstance(item, dict):
            continue
        d = item.get("data")
        if not isinstance(d, dict):
            continue

        # Filter by parametertype_id if requested
        if restrict_param_ids is not None:
            pid = d.get("parametertype_id")
            try:
                pid_int = int(pid)
            except Exception:
                # Skip if pid is missing or not an int
                continue
            if pid_int not in restrict_param_ids:
                continue

        current = d.get("DDF_unit")
        if only_missing:
            # Treat "", "null" (string), and None as missing
            missing = (current is None) or (isinstance(current, str) and current.strip().lower() in ("", "null"))
            if not missing:
                continue

        d["DDF_unit"] = new_unit  # can be None (-> JSON null)
        updated += 1

    return updated, len(rules)


def save_rules(data: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def default_out_path(in_path: Path, label: str) -> Path:
    stem = in_path.stem  # e.g., Rules_20251105
    return in_path.with_name(f"{stem}_{label}.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update DDF_unit for every (or targeted) rule in a Rules JSON file."
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        required=True,
        help="Path to input Rules JSON (e.g., Rules_20251105.json)",
    )

    # Mutually exclusive: set a unit string or clear to null
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--unit",
        dest="unit",
        help="New unit string to set (e.g., 'mg/kg').",
    )
    g.add_argument(
        "--clear",
        action="store_true",
        help="Clear DDF_unit to null.",
    )

    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only update rules where DDF_unit is currently missing (None/''/'null').",
    )
    parser.add_argument(
        "--parametertype-id",
        nargs="*",
        help="Restrict updates to these parametertype_id values (space-separated). Example: --parametertype-id 101 202 303",
    )

    parser.add_argument(
        "--out",
        dest="out_path",
        default=None,
        help="Output JSON path. If omitted, a suffix is auto-generated.",
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

    # Determine new unit value and output label
    if args.clear:
        new_unit: Optional[str] = None
        label = "unit_null"
    else:
        new_unit = str(args.unit)
        safe = new_unit.replace("/", "").replace(" ", "")
        label = f"unit_{safe}"

    out_path: Path
    if args.inplace:
        out_path = in_path
    elif args.out_path is not None:
        out_path = Path(args.out_path)
    else:
        out_path = default_out_path(in_path, label)

    restrict_ids = parse_param_ids(args.parametertype_id)

    data = load_rules(in_path)
    updated, total = update_unit(
        data,
        new_unit=new_unit,
        only_missing=bool(args.only_missing),
        restrict_param_ids=restrict_ids,
    )
    save_rules(data, out_path)

    print(f"Total rules: {total}")
    print(f"Updated DDF_unit in: {updated} rules")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
