#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import List

import pandas as pd


def add_perfect_and_not_ok_rules(
    input_path: str,
    output_path: str,
    threshold: float = 0.01,
) -> None:
    """
    For each row whose normalized DDF_type == 'perfect' and missing operator,
    set operator '<=' and value = threshold, then insert a 'not OK' row
    directly underneath with operator '>' and the same threshold.
    """

    df: pd.DataFrame = pd.read_csv(input_path)

    new_rows: List[dict] = []

    for _, row in df.iterrows():
        row_dict: dict = row.to_dict()

        raw_ddf_type = row_dict.get("DDF_type")
        # Normalize: handle None/NaN, strip spaces, lowercase
        ddf_type_norm: str = (
            str(raw_ddf_type).strip().lower() if raw_ddf_type is not None else ""
        )

        operator = row_dict.get("operator")

        # Only touch rows that are 'perfect' (normalized) and have no operator yet
        if ddf_type_norm == "perfect" and (
            pd.isna(operator) or operator == ""  # type: ignore[arg-type]
        ):
            # Update this perfect row
            row_dict["DDF_type"] = raw_ddf_type.strip() if isinstance(raw_ddf_type, str) else "perfect"
            row_dict["operator"] = "<="
            row_dict["value"] = threshold

            if not row_dict.get("color"):
                row_dict["color"] = "green"

            new_rows.append(row_dict)

            # Create matching not OK row underneath
            not_ok_row: dict = row_dict.copy()
            not_ok_row["DDF_type"] = "not OK"
            not_ok_row["color"] = "red"
            not_ok_row["operator"] = ">"
            not_ok_row["value"] = threshold

            new_rows.append(not_ok_row)

        else:
            # Leave all other rows (including GC/LC summary lines) unchanged
            new_rows.append(row_dict)

    out_df: pd.DataFrame = pd.DataFrame(new_rows)
    out_df.to_csv(output_path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add perfect/not OK rules (<= threshold / > threshold) for pesticides template."
    )
    parser.add_argument(
        "--in",
        "--input",
        dest="input_path",
        required=True,
        help="Path to input CSV file.",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        required=True,
        help="Path for output CSV file.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.01,
        help="Threshold value to use for rules (default: 0.01).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    add_perfect_and_not_ok_rules(
        input_path=args.input_path,
        output_path=args.output_path,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
