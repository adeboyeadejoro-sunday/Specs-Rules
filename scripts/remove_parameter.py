#!/usr/bin/env python3
import json
import argparse
from typing import Any, Dict, List

def remove_params_from_json(input_path: str, param_ids: List[int], output_path: str) -> None:
    """Remove all rules from a JSON file where data.parametertype_id matches any in param_ids."""
    with open(input_path, "r", encoding="utf-8") as infile:
        data: Dict[str, Any] = json.load(infile)

    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError("Invalid JSON format: missing 'rules' list")

    original_count: int = len(data["rules"])
    data["rules"] = [
        rule for rule in data["rules"]
        if rule.get("data", {}).get("parametertype_id") not in param_ids
    ]
    removed_count: int = original_count - len(data["rules"])

    with open(output_path, "w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=2, ensure_ascii=False)

    removed_list = ", ".join(map(str, param_ids))
    print(f"Removed {removed_count} rule(s) with parametertype_id in [{removed_list}]")
    print(f"Output written to {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove parameter rules from a JSON file by one or more parametertype_id values"
    )
    parser.add_argument("--in", dest="input", required=True, help="Path to input JSON file")
    parser.add_argument("--param-id", type=int, nargs="+", required=True,
                        help="One or more Parameter IDs to remove (space-separated)")
    parser.add_argument("--out", required=True, help="Path to output JSON file")

    args = parser.parse_args()
    remove_params_from_json(args.input, args.param_id, args.out)

if __name__ == "__main__":
    main()
