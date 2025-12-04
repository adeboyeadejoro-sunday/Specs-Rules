#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

Number = Union[int, float]


@dataclass
class ExportResult:
    """
    Holds output file paths for the JSON exports (either or both may be None).
    """
    specs_json: Optional[Path]
    rules_json: Optional[Path]


class SpecsRulesExporter:
    """
    Read one or more Specs and/or Rules CSVs and export merged JSON files that match
    the structure produced by your Apps Script.

    - You can pass multiple Specs CSV inputs and get ONE merged Specs JSON.
    - You can pass multiple Rules CSV inputs and get ONE merged Rules JSON.
    - Rows are deduplicated across all files (based on cleaned row contents).
    - Column sets must be identical across all CSVs of the same type:
      * same headers after lowercasing and stripping whitespace
      * any extra/missing column -> hard error
      * different order but same set -> allowed with a warning
    - For 'Specs', 'translations' is a JSON STRING.
    - For 'Rules', numeric coercion and null handling match previous behavior.
    """

    def __init__(
        self,
        specs_csvs: Optional[Iterable[Union[str, Path]]] = None,
        rules_csvs: Optional[Iterable[Union[str, Path]]] = None,
        out_specs: Optional[Union[str, Path]] = None,
        out_rules: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Parameters
        ----------
        specs_csvs : iterable of str | Path | None
            One or more paths to Specs CSV files. May be None if you only export Rules.
        rules_csvs : iterable of str | Path | None
            One or more paths to Rules CSV files. May be None if you only export Specs.
        out_specs : str | Path | None
            Target Specs JSON file path (before auto _1, _2 suffixing).
        out_rules : str | Path | None
            Target Rules JSON file path (before auto _1, _2 suffixing).
        """
        self.specs_csvs: List[Path] = [Path(p) for p in specs_csvs] if specs_csvs is not None else []
        self.rules_csvs: List[Path] = [Path(p) for p in rules_csvs] if rules_csvs is not None else []

        self.out_specs: Optional[Path] = Path(out_specs) if out_specs is not None else None
        self.out_rules: Optional[Path] = Path(out_rules) if out_rules is not None else None

    # --------------------------- Public API ---------------------------

    def run(self) -> ExportResult:
        """
        Execute pipeline for whichever CSVs were provided.
        Creates ONE Specs JSON and/or ONE Rules JSON from all inputs.

        Returns
        -------
        ExportResult
            Paths to the JSON files created; each may be None if that type wasn't supplied.
        """
        if not self.specs_csvs and not self.rules_csvs:
            raise ValueError("Provide at least one of specs_csvs or rules_csvs.")

        specs_path: Optional[Path] = None
        rules_path: Optional[Path] = None

        # Specs branch
        if self.specs_csvs:
            if self.out_specs is None:
                raise ValueError("out_specs must be provided when specs_csvs are given.")
            specs_rows: List[Dict[str, Any]] = self._read_and_merge_csvs(self.specs_csvs, kind="Specs")
            specs_payload: Dict[str, Any] = self._build_specs_payload(specs_rows)
            final_specs_path: Path = self._get_unique_out_path(self.out_specs)
            specs_path = self._save_json(specs_payload, final_specs_path)

        # Rules branch
        if self.rules_csvs:
            if self.out_rules is None:
                raise ValueError("out_rules must be provided when rules_csvs are given.")
            rules_rows: List[Dict[str, Any]] = self._read_and_merge_csvs(self.rules_csvs, kind="Rules")
            rules_payload: Dict[str, Any] = self._build_rules_payload(rules_rows)
            final_rules_path: Path = self._get_unique_out_path(self.out_rules)
            rules_path = self._save_json(rules_payload, final_rules_path)

        return ExportResult(specs_json=specs_path, rules_json=rules_path)

    # ------------------------- Building payloads -------------------------

    def _build_specs_payload(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Match Apps Script behavior for Specs:
        - type/status/archiviert -> int (or null)
        - order -> None if blank or literal 'null', else keep string
        - translations -> JSON STRING of {"en": {...}} (same as Apps Script)
        """
        items: List[Dict[str, Any]] = []
        for row in rows:
            name: str = self._to_str(row.get("name"))
            item: Dict[str, Any] = {
                "action": "create",
                "data": {
                    "name": name,
                    "type": self._to_int(row.get("type")),
                    "status": self._to_int(row.get("status")),
                    "archiviert": self._to_int(row.get("archiviert")),
                    "order": self._null_if_blank_or_literal_null(row.get("order")),
                    # Keep translations as JSON STRING
                    "translations": json.dumps({
                        "en": {
                            "name": name,
                            "DDF_Defaulttext_OK": "NULL",
                            "DDF_Defaulttext_NOT_OK": "NULL",
                            "DDF_Defaulttext_Toleranzbereich_NOT_OK": "NULL",
                        }
                    }),
                },
            }
            items.append(item)

        return {"specs": items}

    def _build_rules_payload(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Match Apps Script behavior for Rules:
        - Integers: column, inverse, parametertype_id, show, spec_id
        - DDF_target_value, DDF_unit, linker, operator2, regex_filter, text, translations, value2:
          -> None if blank/'null', else keep string
        - value: numeric if can parse, else keep as string (e.g. 'OK'); blank/'null' -> None
        """
        items: List[Dict[str, Any]] = []
        for row in rows:
            data: Dict[str, Any] = {
                "color": self._to_str(row.get("color")),
                "column": self._to_int(row.get("column")),
                "DDF_target_value": self._null_if_blank_or_literal_null(row.get("DDF_target_value")),
                "DDF_type": self._to_str(row.get("DDF_type")),
                "DDF_unit": self._null_if_blank_or_literal_null(row.get("DDF_unit")),
                "inverse": self._to_int(row.get("inverse")),
                "linker": self._null_if_blank_or_literal_null(row.get("linker")),
                "operator": self._to_str(row.get("operator")),
                "operator2": self._null_if_blank_or_literal_null(row.get("operator2")),
                "parametertype_id": self._to_int(row.get("parametertype_id")),
                "regex_filter": self._null_if_blank_or_literal_null(row.get("regex_filter")),
                "show": self._to_int(row.get("show")),
                "spec_id": self._to_int(row.get("spec_id")),
                "text": self._null_if_blank_or_literal_null(row.get("text")),
                "translations": self._null_if_blank_or_literal_null(row.get("translations")),
                "value": self._to_number_or_keep(row.get("value")),
                "value2": self._null_if_blank_or_literal_null(row.get("value2")),
            }
            items.append({"action": "create", "data": data})

        return {"rules": items}

    # ---------------------- CSV reading / merging ----------------------

    def _read_and_merge_csvs(self, paths: List[Path], kind: str) -> List[Dict[str, Any]]:
        """
        Read and merge multiple CSV files of the same kind ('Specs' or 'Rules').

        - Validates that all files have compatible headers:
          * normalize header names by lowercasing + strip
          * if sets differ -> hard error
          * if sets equal but order differs -> soft warning
        - Strips whitespace from every cell.
        - Deduplicates rows across all files (preserve first occurrence).
        """
        if not paths:
            return []

        normalized_header_ref: Optional[List[str]] = None
        original_header_ref: Optional[List[str]] = None

        all_rows: List[Dict[str, Any]] = []

        for idx, path in enumerate(paths):
            if not path.exists():
                raise FileNotFoundError(f"{kind} CSV not found: {path}")

            rows, headers = self._read_single_csv(path)
            normalized_headers: List[str] = [self._normalize_header(h) for h in headers]

            if normalized_header_ref is None:
                # First file becomes reference
                normalized_header_ref = normalized_headers
                original_header_ref = headers
            else:
                # Compare header sets (normalized)
                ref_set: Set[str] = set(normalized_header_ref)
                current_set: Set[str] = set(normalized_headers)

                if ref_set != current_set:
                    raise ValueError(
                        f"Incompatible columns between CSV files for {kind}.\n"
                        f"Reference ({paths[0]}): {original_header_ref}\n"
                        f"Current   ({path}): {headers}"
                    )

                # Same set but different order -> warning
                if normalized_headers != normalized_header_ref:
                    print(
                        f"[WARN] Column order differs between {paths[0]} and {path} — continuing.",
                        file=sys.stderr,
                    )

            all_rows.extend(rows)

        # Deduplicate rows while preserving first occurrence
        deduped_rows: List[Dict[str, Any]] = []
        seen: Set[Tuple[Tuple[str, Any], ...]] = set()

        for row in all_rows:
            # row is already cleaned (values stripped)
            key_tuple: Tuple[Tuple[str, Any], ...] = tuple(sorted(row.items()))
            if key_tuple in seen:
                continue
            seen.add(key_tuple)
            deduped_rows.append(row)

        return deduped_rows

    def _read_single_csv(self, path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Read a single CSV file into cleaned row dicts and return (rows, headers).

        - Skips fully blank lines.
        - Strips whitespace from every cell.
        """
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"CSV '{path}' has no header row.")
            headers: List[str] = list(reader.fieldnames)

            for raw in reader:
                if raw is None:
                    continue

                # Clean each cell: strip whitespace, convert None -> ""
                cleaned: Dict[str, Any] = {}
                for key, value in raw.items():
                    if value is None:
                        cleaned_value: str = ""
                    else:
                        cleaned_value = str(value).strip()
                    cleaned[key] = cleaned_value

                # Check if row is fully blank after stripping
                values_joined: str = "".join(cleaned.values())
                if values_joined.strip() == "":
                    continue

                rows.append(cleaned)

        return rows, headers

    def _normalize_header(self, header: str) -> str:
        """
        Normalize a header for comparison:
        - lowercase
        - strip surrounding whitespace
        """
        return header.strip().lower()

    # --------------------------- I/O helpers ---------------------------

    def _get_unique_out_path(self, requested: Path) -> Path:
        """
        If requested path exists, create a numbered variant:

        merged_specs.json -> merged_specs_1.json -> merged_specs_2.json -> ...
        """
        requested.parent.mkdir(parents=True, exist_ok=True)

        if not requested.exists():
            return requested

        stem: str = requested.stem
        suffix: str = requested.suffix
        parent: Path = requested.parent

        i: int = 1
        while True:
            candidate: Path = parent / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1

    def _save_json(self, payload: Dict[str, Any], out_path: Path) -> Path:
        """
        Save payload as JSON with UTF-8 encoding and pretty indent.

        Parameters
        ----------
        payload : Dict[str, Any]
            The data to serialize.
        out_path : Path
            Where to write the file.

        Returns
        -------
        Path
            The written file path.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return out_path

    # ---------------------- Coercion / conversion ----------------------

    def _null_if_blank_or_literal_null(self, value: Any) -> Optional[str]:
        """
        Convert '', None, 'null' (any case, with optional surrounding spaces) -> None.
        Otherwise return the original value as string.

        NOTE: whitespace has already been stripped from cell values on read.
        """
        if value is None:
            return None
        s: str = str(value).strip()
        if s == "" or s.lower() == "null":
            return None
        return s

    def _to_int(self, value: Any) -> Optional[int]:
        """
        Convert to int if value is not blank/'null' and is numeric.
        Otherwise return None.
        """
        v: Optional[str] = self._null_if_blank_or_literal_null(value)
        if v is None:
            return None
        try:
            # allow floats like "3.0" to become 3
            n: float = float(v)
            return int(n)
        except Exception:
            return None

    def _to_number_or_keep(self, value: Any) -> Optional[Union[Number, str]]:
        """
        - If blank/'null' -> None
        - If numeric text -> number
        - Else keep original string (e.g., 'OK', 'not OK')
        """
        v: Optional[str] = self._null_if_blank_or_literal_null(value)
        if v is None:
            return None
        try:
            # integer?
            if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
                return int(v)
            # fall back to float
            return float(v)
        except Exception:
            return v  # keep as string

    def _to_str(self, value: Any) -> str:
        """
        Return a string; for None returns empty string.
        """
        if value is None:
            return ""
        return str(value)


# ------------------------------- CLI usage -------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export merged Specs and/or Rules JSON from one or more CSV files "
            "(Apps Script-compatible structure)."
        )
    )

    # Multiple Specs CSVs
    parser.add_argument(
        "--specs",
        nargs="+",
        default=None,
        help=(
            "Path(s) to Specs CSV file(s). "
            "When provided, --out-specs is required. "
            "All Specs CSVs must have the same columns (case-insensitive, ignoring spaces)."
        ),
    )

    # Multiple Rules CSVs
    parser.add_argument(
        "--rules",
        nargs="+",
        default=None,
        help=(
            "Path(s) to Rules CSV file(s). "
            "When provided, --out-rules is required. "
            "All Rules CSVs must have the same columns (case-insensitive, ignoring spaces)."
        ),
    )

    # Explicit output paths
    parser.add_argument(
        "--out-specs",
        dest="out_specs",
        default=None,
        help=(
            "Path to merged Specs JSON output. "
            "If the file already exists, a numbered variant will be created "
            "(e.g., merged_specs_1.json, merged_specs_2.json)."
        ),
    )

    parser.add_argument(
        "--out-rules",
        dest="out_rules",
        default=None,
        help=(
            "Path to merged Rules JSON output. "
            "If the file already exists, a numbered variant will be created "
            "(e.g., merged_rules_1.json, merged_rules_2.json)."
        ),
    )

    args = parser.parse_args()

    specs_paths_raw: Optional[List[str]] = args.specs
    rules_paths_raw: Optional[List[str]] = args.rules

    if specs_paths_raw is None and rules_paths_raw is None:
        parser.error("You must provide at least one of --specs or --rules.")

    # Enforce that when inputs exist, corresponding outputs are provided
    if specs_paths_raw is not None and args.out_specs is None:
        parser.error("--out-specs is required when --specs is provided.")
    if rules_paths_raw is not None and args.out_rules is None:
        parser.error("--out-rules is required when --rules is provided.")

    exporter = SpecsRulesExporter(
        specs_csvs=specs_paths_raw,
        rules_csvs=rules_paths_raw,
        out_specs=args.out_specs,
        out_rules=args.out_rules,
    )

    result: ExportResult = exporter.run()

    if result.specs_json is not None:
        print(f"Wrote Specs JSON: {result.specs_json}")
    if result.rules_json is not None:
        print(f"Wrote Rules JSON: {result.rules_json}")


if __name__ == "__main__":
    main()
