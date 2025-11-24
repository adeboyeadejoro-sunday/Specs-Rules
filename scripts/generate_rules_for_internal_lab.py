#!/usr/bin/env python3
import json
import argparse
from typing import List, Dict, Any


def generate_rules(
    input_path: str,
    spec_id: int,
    targets: List[float],
    output_path: str
) -> None:
    """
    Load template rules, insert spec_id and target values, and write output JSON.

    Parameters
    ----------
    input_path : str
        Path to the template JSON file (e.g. Internal_Lab_Templates.json).

    spec_id : int
        The spec_id value to assign to every rule's data.spec_id.

    targets : List[float]
        One numeric target per parameter.
        Since each parameter has 2 rules (perfect + not OK),
        the number of targets must equal len(rules) // 2.

    output_path : str
        Path to write the processed JSON (e.g. Internal_Lab_Rules_Final.json).
    """

    # Load template
    with open(input_path, "r", encoding="utf-8") as f:
        template: Dict[str, Any] = json.load(f)

    rules: List[Dict[str, Any]] = template.get("rules", [])

    if len(rules) % 2 != 0:
        raise ValueError("Template format error: rules must come in perfect/not-OK pairs.")

    param_count: int = len(rules) // 2

    if len(targets) != param_count:
        raise ValueError(
            f"Number of targets ({len(targets)}) does not match "
            f"parameter count ({param_count}). "
            "Expected one target per pair of rules."
        )

    # Apply target and spec_id
    for i in range(param_count):
        target_value: float = targets[i]

        # Each parameter has 2 rules: perfect + not OK
        perfect_rule_index: int = i * 2
        not_ok_rule_index: int = perfect_rule_index + 1

        # perfect rule
        perfect_rule: Dict[str, Any] = rules[perfect_rule_index]
        perfect_rule_data: Dict[str, Any] = perfect_rule.get("data", {})
        perfect_rule_data["spec_id"] = spec_id
        perfect_rule_data["value"] = target_value
        perfect_rule_data["DDF_target_value"] = target_value
        perfect_rule["data"] = perfect_rule_data

        # not OK rule
        not_ok_rule: Dict[str, Any] = rules[not_ok_rule_index]
        not_ok_rule_data: Dict[str, Any] = not_ok_rule.get("data", {})
        not_ok_rule_data["spec_id"] = spec_id
        not_ok_rule_data["value"] = target_value
        not_ok_rule_data["DDF_target_value"] = target_value
        not_ok_rule["data"] = not_ok_rule_data

    # Write final output
    output_obj: Dict[str, Any] = {"rules": rules}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_obj, f, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Arguments (command line)
    ------------------------
    --from : str
        Input template JSON path.
        (Named '--from' to match your example; internally mapped to input_path.)

    --spec-id : int
        Spec ID to apply to each rule.

    --targets : str
        A list such as "[0.55, 2, 0.85, 90]".
        This will be parsed into a Python list of floats.

    --out : str
        Output file path.
    """
    parser = argparse.ArgumentParser(description="Generate rules for internal lab")

    parser.add_argument(
        "--from",
        dest="input_path",
        required=True,
        help="Path to template JSON (e.g. Internal_Lab_Templates.json)",
    )

    parser.add_argument(
        "--spec-id",
        dest="spec_id",
        required=True,
        type=int,
        help="Spec ID to assign to every rule",
    )

    parser.add_argument(
        "--targets",
        dest="targets",
        required=True,
        type=str,
        help='List of numeric targets, e.g. "[0.55, 2, 0.85, 90]"',
    )

    parser.add_argument(
        "--out",
        dest="output_path",
        required=True,
        help="Path to output JSON (e.g. Internal_Lab_Rules_Final.json)",
    )

    return parser.parse_args()


def parse_targets(targets_str: str) -> List[float]:
    """
    Convert a string like "[0.55, 2, 0.85, 90]" into a list of floats.

    Parameters
    ----------
    targets_str : str
        Raw string from the command line.

    Returns
    -------
    List[float]
        Parsed target values.
    """
    stripped: str = targets_str.strip()
    # Remove surrounding brackets if present
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]

    if not stripped:
        return []

    parts: List[str] = [p.strip() for p in stripped.split(",") if p.strip()]

    return [float(p) for p in parts]


def main() -> None:
    args: argparse.Namespace = parse_args()

    targets_list: List[float] = parse_targets(args.targets)

    generate_rules(
        input_path=args.input_path,
        spec_id=args.spec_id,
        targets=targets_list,
        output_path=args.output_path,
    )


if __name__ == "__main__":
    main()
