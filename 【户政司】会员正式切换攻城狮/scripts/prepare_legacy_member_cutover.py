#!/usr/bin/env python3
"""Prepare deterministic member and historical-order artifacts for HKP cutover."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
MEMBER_CONVERTER = SCRIPT_DIR / "convert_legacy_member_exports.py"
ORDER_CONVERTER = SCRIPT_DIR / "import_legacy_consumption_orders.py"
REQUIRED_EXCLUDED_ACCOUNT_TYPES = {"公益账户"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def count_issue_severities(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            severity = (row.get("severity") or "UNKNOWN").upper()
            counts[severity] = counts.get(severity, 0) + 1
    return counts


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_account_mapping(member_summary: dict) -> None:
    accounts = member_summary["accounts"]
    type_counts = accounts.get("type_counts", {})
    excluded_type_counts = accounts.get("excluded_type_counts", {})
    explicit_types = set(accounts.get("explicitly_excluded_account_types", []))
    checks = {
        "detail_rows_match_imported": (
            member_summary["counts"].get("legacy_account_detail") == accounts.get("imported_rows")
        ),
        "row_partition_matches": (
            accounts.get("imported_rows", 0) + accounts.get("excluded_rows", 0) == accounts.get("total_rows", 0)
        ),
        "excluded_type_counts_match_rows": (
            sum(excluded_type_counts.values()) == accounts.get("excluded_rows", 0)
        ),
        "required_exclusions_declared": REQUIRED_EXCLUDED_ACCOUNT_TYPES.issubset(explicit_types),
        "explicit_types_fully_excluded": all(
            excluded_type_counts.get(account_type, 0) == type_counts.get(account_type, 0)
            for account_type in explicit_types
        ),
    }
    if not all(checks.values()):
        raise SystemExit("account artifact mapping validation failed: " + json.dumps(checks, ensure_ascii=False))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--members", required=True, type=Path)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--accounts", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--batch-code", default="")
    args = parser.parse_args(argv)

    for source in (args.members, args.orders, args.accounts):
        if not source.is_file():
            raise SystemExit(f"source workbook not found: {source}")

    generated_at = dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")
    batch_code = args.batch_code or "HKP_LEGACY_CUTOVER_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    args.out.mkdir(parents=True, exist_ok=True)
    order_out = args.out / "orders"

    run([
        sys.executable,
        str(MEMBER_CONVERTER),
        "--members", str(args.members),
        "--orders", str(args.orders),
        "--accounts", str(args.accounts),
        "--out", str(args.out),
        "--batch-code", batch_code,
    ])
    run([
        sys.executable,
        str(ORDER_CONVERTER),
        "--orders-xlsx", str(args.orders),
        "--out", str(order_out),
    ])

    member_summary = load_json(args.out / "validation_summary.json")
    order_summary = load_json(order_out / "validation_summary.json")
    member_issues = count_issue_severities(args.out / "validation_issues.csv")
    order_issues = count_issue_severities(order_out / "validation_issues.csv")

    if member_issues.get("ERROR", 0) or order_issues.get("ERROR", 0):
        raise SystemExit("cutover artifacts contain ERROR validation issues")
    if member_summary["orders"]["missing_member_refs"] != 0:
        raise SystemExit("consumption workbook contains missing member references")
    if member_summary["accounts"]["missing_member_refs"] != 0:
        raise SystemExit("account workbook contains missing member references")
    validate_account_mapping(member_summary)
    if order_summary["counts"]["legacy_consumption_orders"] != member_summary["orders"]["total_rows"]:
        raise SystemExit("member and order converters disagree on consumption row count")
    if order_summary["orders"]["valid_positive_amount_cent"] != member_summary["orders"]["valid_amount_cent"]:
        raise SystemExit("member and order converters disagree on valid consumption amount")

    output_files = sorted(
        path for path in args.out.rglob("*")
        if path.is_file() and path.name != "cutover_manifest.json"
    )
    manifest = {
        "batch_code": batch_code,
        "generated_at": generated_at,
        "sources": {
            "members": {"path": str(args.members), "sha256": sha256(args.members)},
            "orders": {"path": str(args.orders), "sha256": sha256(args.orders)},
            "accounts": {"path": str(args.accounts), "sha256": sha256(args.accounts)},
        },
        "member_issue_severities": member_issues,
        "order_issue_severities": order_issues,
        "member_summary": member_summary,
        "order_summary": order_summary,
        "outputs": {
            str(path.relative_to(args.out)): {
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in output_files
        },
    }
    manifest_path = args.out / "cutover_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "batch_code": batch_code,
        "artifact_dir": str(args.out),
        "members": member_summary["counts"]["crm_member_profile"],
        "orders": order_summary["counts"]["legacy_consumption_orders"],
        "accounts": member_summary["accounts"]["total_rows"],
        "member_issues": member_issues,
        "order_issues": order_issues,
        "manifest": str(manifest_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
