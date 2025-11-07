#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union


Json = Dict[str, Any]


# -------------------- Utilities: dot-path get/set --------------------
def _split_path(path: str) -> List[str]:
    if not path or path.strip() == "":
        raise ValueError("Key path must be non-empty, e.g. 'action' or 'data.spec_id'.")
    return [p for p in path.split(".") if p]


def get_by_path(obj: Any, path: Sequence[str]) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def set_by_path(obj: Dict[str, Any], path: Sequence[str], value: Any) -> None:
    cur: Dict[str, Any] = obj
    for key in path[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]  # type: ignore[assignment]
    cur[path[-1]] = value


# -------------------- Value parsing / coercion --------------------
def parse_value(raw: str, as_type: str) -> Any:
    """
    Parse CLI --value according to --as.
    as_type: auto | str | int | float | bool | null | json
    """
    t = as_type.lower()
    if t == "str":
        return raw
    if t == "int":
        return int(raw)
    if t == "float":
        return float(raw)
    if t == "bool":
        low = raw.strip().lower()
        if low in ("true", "1", "yes", "y", "on"):
            return True
        if low in ("false", "0", "no", "n", "off"):
            return False
        raise ValueError(f"Cannot parse boolean from {raw!r}")
    if t == "null":
        return None
    if t == "json":
        # interpret as JSON literal (object/array/number/bool/null/string)
        return json.loads(raw)

    # auto
    low = raw.strip().lower()
    if low in ("null", ""):
        return None
    if low in ("true", "false"):
        return low == "true"
    # int?
    try:
        if raw.strip().startswith(("+", "-")):
            int(raw)  # raise if not int-like
            return int(raw)
        if raw.isdigit():
            return int(raw)
    except Exception:
        pass
    # float?
    try:
        return float(raw)
    except Exception:
        pass
    # fallback string
    return raw


# -------------------- Param filter (common need) --------------------
def parse_param_ids(values: Optional[Iterable[str]]) -> Optional[Set[int]]:
    if not values:
        return None
    out: Set[int] = set()
    for v in values:
        v = v.strip()
        if v:
            out.add(int(v))
    return out if out else None


def param_id_matches(item: Dict[str, Any], restrict_ids: Optional[Set[int]]) -> bool:
    if restrict_ids is None:
        return True
    data = item.get("data")
    if not isinstance(data, dict):
        return False
    pid = data.get("parametertype_id")
    try:
        return int(pid) in restrict_ids
    except Exception:
        return False


# -------------------- Core update --------------------
def update_key_for_rules(
    payload: Json,
    key_path: str,
    new_value: Any,
    *,
    only_missing: bool = False,
    restrict_param_ids: Optional[Set[int]] = None,
) -> Tuple[int, int]:
    """
    Update a key (by dot-path) in every item of payload['rules'].

    Returns (updated_count, total_rules).
    """
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Input JSON must have top-level 'rules' list.")

    path = _split_path(key_path)
    updated = 0
    for item in rules:
        if not isinstance(item, dict):
            continue
        if not param_id_matches(item, restrict_param_ids):
            continue

        current = get_by_path(item, path)
        if only_missing:
            missing = (current is None) or (isinstance(current, str) and current.strip().lower() in ("", "null"))
            if not missing:
                continue

        set_by_path(item, path, new_value)
        updated += 1

    return updated, len(rules)


# -------------------- I/O --------------------
def load_rules(path: Path) -> Json:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_rules(data: Json, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def default_out_path(in_path: Path, key_path: str, value_label: str) -> Path:
    stem = in_path.stem  # e.g., Rules_20251105
    safe_key = key_path.replace(".", "_")
    safe_val = value_label.replace("/", "").replace(" ", "")
    return in_path.with_name(f"{stem}_{safe_key}_{safe_val}.json")


# -------------------- CLI --------------------
def main() -> None:
    p = argparse.ArgumentParser(
        description="Update any key in each rule of a Rules JSON (supports dot-paths and typed values)."
    )
    p.add_argument("--in", dest="in_path", required=True, help="Input Rules JSON, e.g., Rules_20251105.json")
    p.add_argument("--key", required=True, help="Key to update per rule. Dot-path allowed, e.g. 'action' or 'data.spec_id'")
    p.add_argument(
        "--value",
        required=True,
        help="New value. Use --as to control type. For --as json, provide a JSON literal.",
    )
    p.add_argument(
        "--as",
        dest="as_type",
        choices=["auto", "str", "int", "float", "bool", "null", "json"],
        default="auto",
        help="How to interpret --value. Default: auto",
    )
    p.add_argument("--only-missing", action="store_true", help="Only set where the key is missing/empty/null.")
    p.add_argument(
        "--parametertype-id",
        nargs="*",
        help="Restrict updates to these parametertype_id values (space-separated). Example: --parametertype-id 101 202",
    )
    p.add_argument("--out", dest="out_path", default=None, help="Output JSON path.")
    p.add_argument("--inplace", action="store_true", help="Overwrite the input file (mutually exclusive with --out).")

    args = p.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")

    if args.inplace and args.out_path is not None:
        raise SystemExit("Use either --inplace or --out, not both.")

    new_val = parse_value(args.value, args.as_type)
    data = load_rules(in_path)

    restrict_ids = parse_param_ids(args.parametertype_id)
    updated, total = update_key_for_rules(
        data,
        key_path=args.key,
        new_value=new_val,
        only_missing=bool(args.only_missing),
        restrict_param_ids=restrict_ids,
    )

    # Default output name if not specified
    if args.inplace:
        out_path = in_path
    else:
        if args.out_path is not None:
            out_path = Path(args.out_path)
        else:
            # For label, reuse the raw --value to make it readable in filename
            out_path = default_out_path(in_path, args.key, str(args.value))

    save_rules(data, out_path)

    print(f"Total rules: {total}")
    print(f"Updated '{args.key}' in: {updated} rules")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
