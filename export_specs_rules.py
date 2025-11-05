from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union


Number = Union[int, float]


@dataclass
class ExportResult:
    """Holds output file paths for the JSON exports (either or both may be None)."""
    specs_json: Optional[Path]
    rules_json: Optional[Path]


class SpecsRulesExporter:
    """
    Read Specs and/or Rules CSVs and export JSON files that match the
    structure produced by your Apps Script.

    - For 'Specs', the 'translations' field is a JSON **string** (not an object),
      matching your Apps Script's `JSON.stringify({...})` behavior.
    - For 'Rules', values are coerced to numbers when possible, or kept as strings;
      'null' (literal) and blanks become None (-> null in JSON).
    """

    def __init__(
        self,
        specs_csv: Optional[Union[str, Path]] = None,
        rules_csv: Optional[Union[str, Path]] = None,
        out_dir: Union[str, Path] = ".",
    ) -> None:
        """
        Parameters
        ----------
        specs_csv : str | Path | None
            Path to Specs CSV (optional).
        rules_csv : str | Path | None
            Path to Rules CSV (optional).
        out_dir : str | Path
            Directory to write output JSON files.
        """
        self.specs_csv: Optional[Path] = Path(specs_csv) if specs_csv is not None else None
        self.rules_csv: Optional[Path] = Path(rules_csv) if rules_csv is not None else None
        self.out_dir: Path = Path(out_dir)

    # --------------------------- Public API ---------------------------

    def run(self) -> ExportResult:
        """
        Execute pipeline for whichever CSVs were provided.
        Creates 'Specs_YYYYMMDD.json' and/or 'Rules_YYYYMMDD.json' in out_dir.

        Returns
        -------
        ExportResult
            Paths to the JSON files created; each may be None if that CSV wasn't supplied.
        """
        if self.specs_csv is None and self.rules_csv is None:
            raise ValueError("Provide at least one of specs_csv or rules_csv.")

        today = datetime.now().strftime("%Y%m%d")
        specs_path: Optional[Path] = None
        rules_path: Optional[Path] = None

        if self.specs_csv is not None:
            specs_rows = self._read_csv(self.specs_csv)
            specs_payload = self._build_specs_payload(specs_rows)
            specs_path = self._save_json(specs_payload, self.out_dir / f"Specs_{today}.json")

        if self.rules_csv is not None:
            rules_rows = self._read_csv(self.rules_csv)
            rules_payload = self._build_rules_payload(rules_rows)
            rules_path = self._save_json(rules_payload, self.out_dir / f"Rules_{today}.json")

        return ExportResult(specs_json=specs_path, rules_json=rules_path)

    def convert_specs(self, specs_csv: Union[str, Path]) -> Path:
        """
        Convert only a Specs CSV to JSON.

        Parameters
        ----------
        specs_csv : str | Path
            Path to the Specs CSV file.

        Returns
        -------
        Path
            Written JSON path.
        """
        rows = self._read_csv(Path(specs_csv))
        payload = self._build_specs_payload(rows)
        out = self.out_dir / f"Specs_{datetime.now().strftime('%Y%m%d')}.json"
        return self._save_json(payload, out)

    def convert_rules(self, rules_csv: Union[str, Path]) -> Path:
        """
        Convert only a Rules CSV to JSON.

        Parameters
        ----------
        rules_csv : str | Path
            Path to the Rules CSV file.

        Returns
        -------
        Path
            Written JSON path.
        """
        rows = self._read_csv(Path(rules_csv))
        payload = self._build_rules_payload(rows)
        out = self.out_dir / f"Rules_{datetime.now().strftime('%Y%m%d')}.json"
        return self._save_json(payload, out)

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
            name = self._to_str(row.get("name"))
            item = {
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
                            "DDF_Defaulttext_Toleranzbereich_NOT_OK": "NULL"
                        }
                    })
                }
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
            data = {
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

    # --------------------------- I/O helpers ---------------------------

    def _read_csv(self, path: Path) -> List[Dict[str, Any]]:
        """
        Read a CSV file into a list of dict rows (header -> cell).
        Skips fully blank lines.

        Parameters
        ----------
        path : Path
            CSV file path.

        Returns
        -------
        List[Dict[str, Any]]
            List of rows keyed by CSV headers.
        """
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")

        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                if raw is None:
                    continue
                values_joined = "".join([(v or "") for v in raw.values()])
                if values_joined.strip() == "":
                    continue
                rows.append(raw)
        return rows

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
        return out_path

    # ---------------------- Coercion / conversion ----------------------

    def _null_if_blank_or_literal_null(self, value: Any) -> Optional[str]:
        """
        Convert '', None, 'null' (any case, with optional surrounding spaces) -> None.
        Otherwise return the original value as string.
        """
        if value is None:
            return None
        s = str(value).strip()
        if s == "" or s.lower() == "null":
            return None
        return s

    def _to_int(self, value: Any) -> Optional[int]:
        """
        Convert to int if value is not blank/'null' and is numeric.
        Otherwise return None.
        """
        v = self._null_if_blank_or_literal_null(value)
        if v is None:
            return None
        try:
            # allow floats like "3.0" to become 3
            n = float(v)
            return int(n)
        except Exception:
            return None

    def _to_number_or_keep(self, value: Any) -> Optional[Union[Number, str]]:
        """
        - If blank/'null' -> None
        - If numeric text -> number
        - Else keep original string (e.g., 'OK', 'not OK')
        """
        v = self._null_if_blank_or_literal_null(value)
        if v is None:
            return None
        try:
            if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
                return int(v)
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

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Export Specs and/or Rules JSON from CSV files (Apps Script-compatible structure)."
    )
    parser.add_argument("--specs", help="Path to Specs CSV", default=None)
    parser.add_argument("--rules", help="Path to Rules CSV", default=None)
    parser.add_argument("--out", default=".", help="Output directory (default: current directory)")

    args = parser.parse_args()

    if args.specs is None and args.rules is None:
        parser.error("You must provide at least one of --specs or --rules")

    exporter = SpecsRulesExporter(specs_csv=args.specs, rules_csv=args.rules, out_dir=args.out)
    result = exporter.run()

    if result.specs_json:
        print(f"Wrote: {result.specs_json}")
    if result.rules_json:
        print(f"Wrote: {result.rules_json}")

    # Exit with success if at least one file was written
    sys.exit(0)
