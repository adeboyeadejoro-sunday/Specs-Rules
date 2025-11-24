#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_rules(path: Path) -> Dict[str, Any]:
    """Load a Rules JSON file and ensure it has a top-level 'rules' list."""
    with path.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError(f"Input JSON '{path}' does not have a top-level 'rules' list.")
    return data


def update_spec_id(data: Dict[str, Any], new_spec_id: int) -> Tuple[int, int]:
    """
    Replace data.spec_id in every rules[*].data object.

    Returns
    -------
    (updated_count, total_rules)
    """
    rules: List[Any] = data.get("rules", [])
    updated: int = 0
    for item in rules:
        if not isinstance(item, dict):
            continue
        d = item.get("data")
        if isinstance(d, dict):
            d["spec_id"] = int(new_spec_id)
            updated += 1
    return updated, len(rules)


def save_rules(data: Dict[str, Any], out_path: Path) -> None:
    """Write the modified Rules JSON to disk, creating parent dirs if needed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def default_out_path(in_path: Path, new_spec_id: int) -> Path:
    """
    Construct a default output path for a given input and spec_id.

    Example
    -------
    Rules_20251105.json -> Rules_20251105_spec789.json
    """
    stem: str = in_path.stem
    return in_path.with_name(f"{stem}_spec{new_spec_id}.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update spec_id for every rule in one or more Rules JSON files."
    )
    parser.add_argument(
        "--in",
        dest="in_paths",
        nargs="+",  # one or more input paths
        required=True,
        help=(
            "Path(s) to input Rules JSON file(s) "
            "(e.g., Rules_20251105.json other_rules.json ...)"
        ),
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
        help=(
            "Output JSON path. "
            "- With a single input: behaves like the old script.\n"
            "- With multiple inputs: all rules are merged and written to this file."
        ),
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Overwrite each input file in place (mutually exclusive with --out).",
    )
    args = parser.parse_args()

    in_paths_raw: List[str] = args.in_paths
    new_spec_id: int = args.spec_id

    if args.inplace and args.out_path is not None:
        raise SystemExit("Use either --inplace OR --out, not both.")

    in_paths: List[Path] = [Path(p) for p in in_paths_raw]
    for p in in_paths:
        if not p.exists():
            raise FileNotFoundError(f"Input not found: {p}")

    multiple_inputs: bool = len(in_paths) > 1
    merge_to_single_output: bool = multiple_inputs and args.out_path is not None and not args.inplace

    total_files: int = 0
    grand_total_rules: int = 0
    grand_total_updated: int = 0

    if merge_to_single_output:
        # MODE: multiple inputs, single merged output JSON
        combined_rules: List[Any] = []

        for in_path in in_paths:
            data: Dict[str, Any] = load_rules(in_path)
            updated, total = update_spec_id(data, new_spec_id)
            rules_list: List[Any] = data.get("rules", [])
            combined_rules.extend(rules_list)

            total_files += 1
            grand_total_rules += total
            grand_total_updated += updated

            print(f"[{in_path}]")
            print(f"  Total rules: {total}")
            print(f"  Updated spec_id in: {updated} rules")

        out_path: Path = Path(args.out_path)
        combined_data: Dict[str, Any] = {"rules": combined_rules}
        save_rules(combined_data, out_path)

        print(f"\nMerged output written to: {out_path}")
        print("Summary:")
        print(f"  Files processed: {total_files}")
        print(f"  Total rules across all files: {grand_total_rules}")
        print(f"  Total rules updated: {grand_total_updated}")

    else:
        # MODE: per-file processing (single input OR multiple inputs without merge)
        for in_path in in_paths:
            if args.inplace:
                out_path = in_path
            else:
                if args.out_path is not None and not multiple_inputs:
                    # single input + --out
                    out_path = Path(args.out_path)
                else:
                    # default per-file output
                    out_path = default_out_path(in_path, new_spec_id)

            data = load_rules(in_path)
            updated, total = update_spec_id(data, new_spec_id)
            save_rules(data, out_path)

            total_files += 1
            grand_total_rules += total
            grand_total_updated += updated

            print(f"[{in_path}] -> [{out_path}]")
            print(f"  Total rules: {total}")
            print(f"  Updated spec_id in: {updated} rules")

        print("\nSummary:")
        print(f"  Files processed: {total_files}")
        print(f"  Total rules across all files: {grand_total_rules}")
        print(f"  Total rules updated: {grand_total_updated}")


if __name__ == "__main__":
    main()
