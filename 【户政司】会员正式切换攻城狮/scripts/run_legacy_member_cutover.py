#!/usr/bin/env python3
"""Back up, clean, import, and verify HelloKitty legacy-member cutovers."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


CLEANUP_CONFIRMATION = "HKP_DELETE_ALL_ORDERS_COUPONS_MEMBERS"
IMPORT_CONFIRMATION = "HKP_IMPORT_VALIDATED_LEGACY_DATA"
FREEZE_CONFIRMATION = "HKP_FREEZE_PRODUCTION_WRITES"
UNFREEZE_CONFIRMATION = "HKP_RESTORE_PRODUCTION_WRITES"
PG_VERSION_RE = re.compile(r"(\d+)(?:\.\d+)?")
MEMBER_NO_RE = re.compile(r"^[A-Za-z0-9_-]{1,96}$")

TABLE_GROUPS = {
    "orders": [
        "admin_order_aftersale",
        "admin_order_export_task",
        "admin_order_logistics",
        "admin_order_remark",
        "admin_order_review",
        "admin_order_risk",
        "pay_payment_operation_log",
        "pay_payment_refund_record",
        "pay_payment_record",
        "park_order_fulfillment",
        "park_order_inventory_lock",
        "park_order_item",
        "park_order_refund",
        "park_order_status_event",
        "park_order_thirdparty_compensation",
        "thirdparty_pos_shenda_refund_task",
        "thirdparty_pos_mobile_return",
        "thirdparty_pos_mobile_order",
        "park_order",
    ],
    "coupon_operations": [
        "admin_coupon_verification",
        "admin_marketing_coupon_export_task",
        "admin_marketing_coupon_code",
        "admin_marketing_coupon_batch",
        "admin_third_party_coupon_export_task",
        "admin_third_party_coupon_upload_record",
        "admin_third_party_coupon_code",
        "admin_third_party_coupon_batch",
        "crm_coupon_issue_flow_log",
        "crm_coupon_issue_recipient",
        "crm_coupon_issue_shard",
        "crm_coupon_issue_task",
        "crm_member_coupon_instance",
        "promotion_budget_log",
        "promotion_coupon_claim_operation",
        "promotion_coupon_exchange_code",
        "promotion_member_coupon",
        "promotion_refund_return_operation",
        "promotion_snapshot_detail",
        "promotion_snapshot",
    ],
    "fast_pass": [
        "admin_ticket_instance_operation_log",
        "admin_ticket_instance",
    ],
    "members": [
        "admin_marketing_new_user_gift_record",
        "admin_member_code_writeoff",
        "admin_member_export_task",
        "admin_member_growth_record",
        "admin_member_import_task",
        "admin_member_profile_operation_log",
        "crm_legacy_member_bind",
        "crm_member_address",
        "crm_member_favorite_product",
        "crm_member_kcoin_transaction",
        "crm_member_phone_dedup_audit",
        "crm_member_stat",
        "member_annual_card",
        "crm_member_profile",
    ],
}


def all_tables() -> list[str]:
    return list(dict.fromkeys(table for tables in TABLE_GROUPS.values() for table in tables))


def db_env(*, write: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PGHOST", "127.0.0.1")
    env.setdefault("PGPORT", "15432")
    env.setdefault("PGUSER", "hellokitty")
    env.setdefault("PGDATABASE", "hellokitty_park")
    if write:
        options = env.get("PGOPTIONS", "").strip()
        env["PGOPTIONS"] = (options + " -c default_transaction_read_only=off").strip()
    return env


def connection_args() -> list[str]:
    env = db_env()
    return [
        "-h", env["PGHOST"],
        "-p", env["PGPORT"],
        "-U", env["PGUSER"],
        "-d", env["PGDATABASE"],
    ]


def run(
        command: list[str],
        *,
        cwd: Path | None = None,
        capture: bool = False,
        write: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=db_env(write=write),
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )


def psql(
        sql: str,
        *,
        cwd: Path | None = None,
        capture: bool = False,
        write: bool = False,
) -> subprocess.CompletedProcess[str]:
    return run([
        "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-P", "pager=off", "-c", sql,
    ], cwd=cwd, capture=capture, write=write)


def psql_file(path: Path) -> None:
    run([
        "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-P", "pager=off",
        "-f", path.name,
    ], cwd=path.parent, write=True)


def psql_script(script: str) -> None:
    subprocess.run(
        [
            "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-P", "pager=off",
        ],
        env=db_env(write=True),
        check=True,
        text=True,
        input=script,
    )


def psql_scalar(sql: str, *, write: bool = False) -> str:
    result = run([
        "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-At", "-c", sql,
    ], capture=True, write=write)
    return (result.stdout or "").strip()


def database_identity() -> dict:
    raw = psql_scalar(
        "SELECT json_build_object("
        "'database', current_database(), "
        "'role', current_user, "
        "'databaseOid', (SELECT oid FROM pg_database WHERE datname = current_database()), "
        "'serverAddress', COALESCE(inet_server_addr()::text, ''), "
        "'serverPort', inet_server_port(), "
        "'serverVersionNum', current_setting('server_version_num'), "
        "'postmasterStartedAt', pg_postmaster_start_time()"
        ")::text"
    )
    return json.loads(raw)


def cutover_target() -> dict:
    env = db_env()
    return {
        "host": env["PGHOST"],
        "port": env["PGPORT"],
        "database": env["PGDATABASE"],
        "role": env["PGUSER"],
        "serverIdentity": database_identity(),
    }


def role_default_read_only() -> str:
    return psql_scalar(
        "SELECT COALESCE((SELECT split_part(setting, '=', 2) "
        "FROM unnest(rolconfig) AS setting "
        "WHERE setting LIKE 'default_transaction_read_only=%'), 'off') "
        "FROM pg_roles WHERE rolname = current_user"
    )


def terminate_other_database_sessions() -> int:
    value = psql_scalar(
        "SELECT COUNT(*) FROM ("
        "SELECT pg_terminate_backend(pid) AS terminated "
        "FROM pg_stat_activity "
        "WHERE datname = current_database() AND pid <> pg_backend_pid()"
        ") t WHERE terminated",
        write=True,
    )
    return int(value)


def freeze_writes(state_file: Path, confirmation: str) -> None:
    if confirmation != FREEZE_CONFIRMATION:
        raise SystemExit(f"freeze requires --confirm {FREEZE_CONFIRMATION}")
    if state_file.exists():
        raise SystemExit(f"freeze state file already exists: {state_file}")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    other_roles = int(psql_scalar(
        "SELECT COUNT(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND pid <> pg_backend_pid() AND usename <> current_user"
    ))
    if other_roles:
        raise SystemExit(f"write freeze blocked: {other_roles} connections use another database role")
    initial_setting = role_default_read_only()
    try:
        psql("ALTER ROLE CURRENT_USER SET default_transaction_read_only = on", write=True)
        terminated = terminate_other_database_sessions()
        if psql_scalar("SHOW default_transaction_read_only") != "on":
            raise SystemExit("write freeze verification failed")
        state = {
            "status": "frozen",
            "phase": "frozen",
            "data_mutated": False,
            "frozen_at": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
            "target": cutover_target(),
            "initial_default_transaction_read_only": initial_setting,
            "terminated_connections": terminated,
            "inventory_at_freeze": inventory(),
        }
        write_json_atomic(state_file, state)
    except BaseException:
        restore_sql = (
            "ALTER ROLE CURRENT_USER SET default_transaction_read_only = on"
            if initial_setting == "on"
            else "ALTER ROLE CURRENT_USER RESET default_transaction_read_only"
        )
        psql(restore_sql, write=True)
        terminate_other_database_sessions()
        raise
    print(json.dumps(state, ensure_ascii=False, indent=2))


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_freeze_state(state_file: Path, state: dict, **updates: object) -> None:
    state.update(updates)
    write_json_atomic(state_file, state)


def require_frozen_state(state_file: Path) -> dict:
    if not state_file.is_file():
        raise SystemExit(f"freeze state file not found: {state_file}")
    state = load_json(state_file)
    if state.get("status") != "frozen":
        raise SystemExit(f"database is not marked frozen in {state_file}")
    if state.get("target") != cutover_target():
        raise SystemExit("cutover target changed after freeze; do not continue on another database or tunnel")
    require_write_freeze()
    return state


def unfreeze_writes(state_file: Path, confirmation: str, artifact_dir: Path | None) -> None:
    if confirmation != UNFREEZE_CONFIRMATION:
        raise SystemExit(f"unfreeze requires --confirm {UNFREEZE_CONFIRMATION}")
    state = require_frozen_state(state_file)
    if state.get("data_mutated"):
        if state.get("phase") != "verified":
            raise SystemExit("database data changed but cutover verification has not passed; writes remain frozen")
        if artifact_dir is None:
            raise SystemExit("unfreeze after cutover requires --artifacts for a fresh verification")
        verify(artifact_dir)
    initial_setting = state.get("initial_default_transaction_read_only", "off")
    if initial_setting == "on":
        psql("ALTER ROLE CURRENT_USER SET default_transaction_read_only = on", write=True)
    else:
        psql("ALTER ROLE CURRENT_USER RESET default_transaction_read_only", write=True)
    terminated = terminate_other_database_sessions()
    expected = "on" if initial_setting == "on" else "off"
    if psql_scalar("SHOW default_transaction_read_only") != expected:
        raise SystemExit("write unfreeze verification failed")
    write_freeze_state(
        state_file,
        state,
        status="restored",
        restored_at=dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
        restore_terminated_connections=terminated,
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


def require_write_freeze() -> None:
    if psql_scalar("SHOW default_transaction_read_only") != "on":
        raise SystemExit("database writes are not frozen; run freeze before this cutover phase")


def command_version(command: str) -> tuple[int, str] | None:
    try:
        result = subprocess.run(
            [command, "--version"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    output = (result.stdout or "").strip()
    match = PG_VERSION_RE.search(output)
    return (int(match.group(1)), output) if match else None


def server_major_version() -> int:
    result = run([
        "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-At", "-c", "SHOW server_version_num",
    ], capture=True)
    version_num = (result.stdout or "").strip()
    if not version_num.isdigit():
        raise SystemExit(f"cannot determine PostgreSQL server version: {version_num!r}")
    return int(version_num) // 10000


def compatible_pg_tools() -> tuple[str, str, str]:
    server_major = server_major_version()
    configured_dump = os.environ.get("HKP_PG_DUMP", "").strip()
    configured_restore = os.environ.get("HKP_PG_RESTORE", "").strip()
    candidates = [
        configured_dump,
        "/opt/homebrew/opt/libpq/bin/pg_dump",
        "/usr/local/opt/libpq/bin/pg_dump",
        shutil.which("pg_dump") or "",
    ]
    checked: list[str] = []
    for candidate in dict.fromkeys(item for item in candidates if item):
        version = command_version(candidate)
        if version is None:
            continue
        client_major, version_text = version
        checked.append(version_text)
        if client_major < server_major:
            continue
        restore_candidate = configured_restore or str(Path(candidate).with_name("pg_restore"))
        if command_version(restore_candidate) is None:
            continue
        return candidate, restore_candidate, version_text
    detail = "; ".join(checked) if checked else "no pg_dump found"
    raise SystemExit(
        f"PostgreSQL {server_major} compatible pg_dump/pg_restore not found ({detail}); "
        "install Homebrew libpq or set HKP_PG_DUMP and HKP_PG_RESTORE"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory() -> dict[str, int]:
    query = " UNION ALL ".join(
        f"SELECT '{table}' AS table_name, COUNT(*)::bigint AS row_count FROM public.{table}"
        for table in all_tables()
    ) + " ORDER BY table_name"
    result = run([
        "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-At", "-F", "\t", "-c", query,
    ], capture=True)
    counts: dict[str, int] = {}
    for line in (result.stdout or "").splitlines():
        table_name, row_count = line.split("\t", 1)
        counts[table_name] = int(row_count)
    if set(counts) != set(all_tables()):
        missing = sorted(set(all_tables()) - set(counts))
        raise SystemExit(f"inventory is incomplete; missing tables: {missing}")
    return counts


def write_counts(path: Path, counts: dict[str, int]) -> None:
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["group", "table_name", "row_count"])
        table_groups = {table: group for group, tables in TABLE_GROUPS.items() for table in tables}
        for table_name, row_count in sorted(counts.items()):
            writer.writerow([table_groups[table_name], table_name, row_count])


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def backup(output_dir: Path, state_file: Path) -> None:
    state = require_frozen_state(state_file)
    if state.get("phase") != "frozen":
        raise SystemExit(f"backup requires freeze phase; current phase={state.get('phase')}")
    pg_dump_bin, pg_restore_bin, pg_dump_version = compatible_pg_tools()
    output_dir.mkdir(parents=True, exist_ok=False)
    before_counts = inventory()
    dump_path = output_dir / "hellokitty_park_before.dump"
    run([
        pg_dump_bin, *connection_args(), "--format=custom", "--no-owner", "--no-privileges", "--file", str(dump_path),
    ])
    run([pg_restore_bin, "--list", str(dump_path)], capture=True)
    after_counts = inventory()
    if before_counts != after_counts:
        write_counts(output_dir / "inventory_before_dump.csv", before_counts)
        write_counts(output_dir / "inventory_after_dump.csv", after_counts)
        raise SystemExit("database changed during backup; freeze writes and create a new backup")
    write_counts(output_dir / "inventory_before.csv", after_counts)
    manifest = {
        "created_at": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
        "database": db_env()["PGDATABASE"],
        "host": db_env()["PGHOST"],
        "port": db_env()["PGPORT"],
        "target": cutover_target(),
        "dump": str(dump_path),
        "dump_size": dump_path.stat().st_size,
        "dump_sha256": sha256(dump_path),
        "pg_dump_version": pg_dump_version,
        "table_groups": TABLE_GROUPS,
        "inventory": after_counts,
    }
    (output_dir / "backup_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_freeze_state(
        state_file,
        state,
        phase="backed_up",
        backup_manifest=str(output_dir / "backup_manifest.json"),
    )
    print(json.dumps({
        "backup_dir": str(output_dir),
        "dump_size": manifest["dump_size"],
        "dump_sha256": manifest["dump_sha256"],
        "rows": sum(after_counts.values()),
    }, ensure_ascii=False, indent=2))


def require_valid_backup(backup_dir: Path) -> dict:
    manifest_path = backup_dir / "backup_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"backup manifest not found: {manifest_path}")
    manifest = load_json(manifest_path)
    if manifest.get("target") != cutover_target():
        raise SystemExit("backup target does not match the current database or tunnel")
    dump_path = Path(manifest["dump"])
    if not dump_path.is_file() or dump_path.stat().st_size == 0:
        raise SystemExit(f"backup dump is missing or empty: {dump_path}")
    if sha256(dump_path) != manifest["dump_sha256"]:
        raise SystemExit("backup dump checksum mismatch")
    _, pg_restore_bin, _ = compatible_pg_tools()
    run([pg_restore_bin, "--list", str(dump_path)], capture=True)
    return manifest


def cleanup(backup_dir: Path, state_file: Path, confirmation: str) -> None:
    if confirmation != CLEANUP_CONFIRMATION:
        raise SystemExit(f"cleanup requires --confirm {CLEANUP_CONFIRMATION}")
    state = require_frozen_state(state_file)
    if state.get("phase") != "backed_up":
        raise SystemExit(f"cleanup requires backed_up phase; current phase={state.get('phase')}")
    expected_manifest = Path(str(state.get("backup_manifest", ""))).resolve()
    supplied_manifest = (backup_dir / "backup_manifest.json").resolve()
    if expected_manifest != supplied_manifest:
        raise SystemExit("cleanup backup does not match the backup recorded in the freeze state")
    manifest = require_valid_backup(backup_dir)
    current_counts = inventory()
    if current_counts != manifest["inventory"]:
        write_counts(backup_dir / "inventory_cleanup_blocked.csv", current_counts)
        raise SystemExit("database changed after backup; create a fresh backup before cleanup")

    write_freeze_state(
        state_file,
        state,
        phase="cleanup_in_progress",
        data_mutated=True,
        cleanup_started_at=dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
    )

    table_sql = ",\n    ".join(f"public.{table}" for table in all_tables())
    sql = f"""BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '0';
TRUNCATE TABLE
    {table_sql}
RESTART IDENTITY;
COMMIT;"""
    try:
        psql(sql, write=True)
    except BaseException:
        try:
            rollback_counts = inventory()
            if rollback_counts == manifest["inventory"]:
                write_counts(backup_dir / "inventory_cleanup_rolled_back.csv", rollback_counts)
                write_freeze_state(
                    state_file,
                    state,
                    phase="backed_up",
                    data_mutated=False,
                    cleanup_rolled_back_at=(
                        dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")
                    ),
                )
        except Exception:
            pass
        raise
    after_counts = inventory()
    non_zero = {table: count for table, count in after_counts.items() if count != 0}
    write_counts(backup_dir / "inventory_after_cleanup.csv", after_counts)
    if non_zero:
        raise SystemExit(f"cleanup verification failed: {non_zero}")
    write_freeze_state(
        state_file,
        state,
        phase="cleaned",
        data_mutated=True,
        cleaned_at=dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
    )
    print(json.dumps({"cleanup": "complete", "tables": len(after_counts), "remaining_rows": 0}, ensure_ascii=False))


def validate_artifacts(artifact_dir: Path) -> tuple[dict, dict]:
    manifest_path = artifact_dir / "cutover_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"cutover manifest not found: {manifest_path}")
    manifest = load_json(manifest_path)
    for relative_path, metadata in manifest["outputs"].items():
        path = artifact_dir / relative_path
        if not path.is_file() or path.stat().st_size != metadata["size"] or sha256(path) != metadata["sha256"]:
            raise SystemExit(f"artifact checksum mismatch: {relative_path}")
    if manifest["member_issue_severities"].get("ERROR", 0):
        raise SystemExit("member artifacts contain ERROR validation issues")
    if manifest["order_issue_severities"].get("ERROR", 0):
        raise SystemExit("order artifacts contain ERROR validation issues")
    validate_account_mapping(manifest["member_summary"])
    return manifest["member_summary"], manifest["order_summary"]


def validate_account_mapping(member_summary: dict) -> None:
    accounts = member_summary["accounts"]
    type_counts = accounts.get("type_counts", {})
    excluded_type_counts = accounts.get("excluded_type_counts", {})
    explicit_types = set(accounts.get("explicitly_excluded_account_types", []))
    required_excluded_types = {"公益账户"}
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
        "required_exclusions_declared": required_excluded_types.issubset(explicit_types),
        "explicit_types_fully_excluded": all(
            excluded_type_counts.get(account_type, 0) == type_counts.get(account_type, 0)
            for account_type in explicit_types
        ),
    }
    if not all(checks.values()):
        raise SystemExit("account artifact mapping validation failed: " + json.dumps(checks, ensure_ascii=False))
    validate_kcoin_mapping(member_summary)


def validate_kcoin_mapping(member_summary: dict) -> None:
    accounts = member_summary["accounts"]
    if accounts.get("source_layout") != "kcoin_account_export":
        return
    profile = member_summary["profile_asset_summary"]
    type_counts = accounts.get("type_counts", {})
    amount_totals = accounts.get("amount_totals", {})
    card_rows = int(type_counts.get("卡币账户", 0))
    card_available_cent = int(amount_totals.get("卡币账户|有效", {}).get("available_balance_cent", 0))
    card_frozen_cent = int(amount_totals.get("卡币账户|冻结", {}).get("available_balance_cent", 0))
    expected_excluded_types = {
        account_type: count
        for account_type, count in type_counts.items()
        if account_type != "卡币账户"
    }
    checks = {
        "card_account_rows_present": card_rows > 0,
        "imported_rows_are_card_only": accounts.get("imported_rows") == card_rows,
        "account_detail_rows_are_card_only": member_summary["counts"].get("legacy_account_detail") == card_rows,
        "excluded_rows_match": accounts.get("excluded_rows") == accounts.get("total_rows", 0) - card_rows,
        "excluded_types_match": accounts.get("excluded_type_counts", {}) == expected_excluded_types,
        "principal_balance_is_zero": profile.get("principal_balance_cent") == 0,
        "activity_coin_balance_is_zero": profile.get("gift_balance_cent") == 0,
        "other_balance_is_zero": profile.get("other_balance_cent") == 0,
        "card_coin_amount_matches": profile.get("card_coin_balance_cent") == card_available_cent,
        "card_balance_matches": profile.get("card_balance_cent") == card_available_cent,
        "frozen_card_coin_matches": profile.get("frozen_balance_cent") == card_frozen_cent,
    }
    if not all(checks.values()):
        raise SystemExit("K-coin artifact mapping validation failed: " + json.dumps(checks, ensure_ascii=False))


def verification_query() -> str:
    return " UNION ALL ".join([
        "SELECT 'crm_member_profile', COUNT(*)::bigint FROM crm_member_profile",
        "SELECT 'crm_member_stat', COUNT(*)::bigint FROM crm_member_stat",
        "SELECT 'crm_legacy_member_bind', COUNT(*)::bigint FROM crm_legacy_member_bind",
        "SELECT 'admin_member_growth_record', COUNT(*)::bigint FROM admin_member_growth_record",
        "SELECT 'park_order', COUNT(*)::bigint FROM park_order",
        "SELECT 'park_order_item', COUNT(*)::bigint FROM park_order_item",
        "SELECT 'park_order_status_event', COUNT(*)::bigint FROM park_order_status_event",
        "SELECT 'points_balance', COALESCE(SUM(points_balance), 0)::bigint FROM crm_member_profile",
        "SELECT 'order_count', COALESCE(SUM(order_count), 0)::bigint FROM crm_member_profile",
        "SELECT 'paid_amount_cent', COALESCE(SUM(paid_amount_cent), 0)::bigint FROM crm_member_profile",
        "SELECT 'park_order_payable_amount_cent', COALESCE(SUM(payable_amount_cent), 0)::bigint FROM park_order",
        "SELECT 'park_order_item_amount_cent', COALESCE(SUM(amount_cent), 0)::bigint FROM park_order_item",
        "SELECT 'principal_balance_cent', COALESCE(SUM(principal_balance_cent), 0)::bigint FROM crm_member_profile",
        "SELECT 'gift_balance_cent', COALESCE(SUM(gift_balance_cent), 0)::bigint FROM crm_member_profile",
        "SELECT 'card_balance_cent', COALESCE(SUM(card_balance_cent), 0)::bigint FROM crm_member_profile",
        "SELECT 'frozen_balance_cent', COALESCE(SUM(frozen_balance_cent), 0)::bigint FROM crm_member_profile",
    ]) + " ORDER BY 1"


def read_verification() -> dict[str, int]:
    result = run([
        "psql", "-X", *connection_args(), "-v", "ON_ERROR_STOP=1", "-At", "-F", "\t", "-c", verification_query(),
    ], capture=True)
    values: dict[str, int] = {}
    for line in (result.stdout or "").splitlines():
        name, value = line.split("\t", 1)
        values[name] = int(value)
    return values


def expected_verification(member_summary: dict, order_summary: dict) -> dict[str, int]:
    profile = member_summary["profile_asset_summary"]
    return {
        "crm_member_profile": member_summary["counts"]["crm_member_profile"],
        "crm_member_stat": member_summary["counts"]["crm_member_stat"],
        "crm_legacy_member_bind": member_summary["counts"]["crm_legacy_member_bind"],
        "admin_member_growth_record": member_summary["counts"]["admin_member_growth_record"],
        "park_order": order_summary["counts"]["legacy_consumption_orders"],
        "park_order_item": order_summary["orders"]["positive_item_rows"],
        "park_order_status_event": order_summary["counts"]["legacy_consumption_orders"],
        "points_balance": profile["points_balance"],
        "order_count": profile["order_count"],
        "paid_amount_cent": profile["paid_amount_cent"],
        "park_order_payable_amount_cent": order_summary["orders"]["positive_amount_cent"],
        "park_order_item_amount_cent": order_summary["orders"]["positive_amount_cent"],
        "principal_balance_cent": profile["principal_balance_cent"],
        "gift_balance_cent": profile["gift_balance_cent"],
        "card_balance_cent": profile["card_balance_cent"],
        "frozen_balance_cent": profile["frozen_balance_cent"],
    }


def verify(artifact_dir: Path, state_file: Path | None = None) -> None:
    state = None
    if state_file is not None:
        state = require_frozen_state(state_file)
        if state.get("phase") not in {"import_in_progress", "imported_unverified", "verified"}:
            raise SystemExit(f"verify requires imported phase; current phase={state.get('phase')}")
    member_summary, order_summary = validate_artifacts(artifact_dir)
    actual = read_verification()
    expected = expected_verification(member_summary, order_summary)
    mismatches = {
        key: {"expected": expected[key], "actual": actual.get(key)}
        for key in expected
        if actual.get(key) != expected[key]
    }
    operational_counts = inventory()
    allowed_non_zero = {
        "admin_member_growth_record",
        "crm_legacy_member_bind",
        "crm_member_stat",
        "crm_member_profile",
        "park_order",
        "park_order_item",
        "park_order_status_event",
    }
    residuals = {
        table: count for table, count in operational_counts.items()
        if table not in allowed_non_zero and count != 0
    }
    report = {
        "verification": "passed" if not mismatches and not residuals else "failed",
        "verified_at": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
        "expected": expected,
        "actual": actual,
        "mismatches": mismatches,
        "unexpected_operational_rows": residuals,
    }
    (artifact_dir / "database_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if mismatches or residuals:
        raise SystemExit(json.dumps({"mismatches": mismatches, "residuals": residuals}, ensure_ascii=False))
    if state_file is not None:
        write_freeze_state(
            state_file,
            state,
            phase="verified",
            verified_at=report["verified_at"],
            verification_report=str(artifact_dir / "database_verification.json"),
        )
    print(json.dumps({"verification": "passed", "actual": actual}, ensure_ascii=False, indent=2))


def verify_legacy_member_binding(member_no: str, out: Path | None) -> None:
    if not MEMBER_NO_RE.fullmatch(member_no):
        raise SystemExit("invalid --member-no")
    sql = f"""
WITH selected_member AS (
    SELECT member_no,
           app_id,
           external_user_id,
           source_channel,
           phone,
           primary_card_no
      FROM crm_member_profile
     WHERE member_no = '{member_no}'
       AND deleted = FALSE
     LIMIT 1
), matching_profiles AS (
    SELECT COUNT(DISTINCT p.member_no) AS profile_count
      FROM crm_member_profile p
      JOIN selected_member selected
        ON p.phone = selected.phone
       AND NULLIF(selected.phone, '') IS NOT NULL
     WHERE p.deleted = FALSE
), bound_identity_profiles AS (
    SELECT COUNT(DISTINCT p.member_no) AS profile_count
      FROM crm_member_profile p
      JOIN selected_member selected
        ON p.app_id = selected.app_id
       AND p.external_user_id = selected.external_user_id
     WHERE p.deleted = FALSE
), legacy_bind AS (
    SELECT COUNT(*) AS bind_count
      FROM crm_legacy_member_bind b
      JOIN selected_member selected
        ON b.member_no = selected.member_no
       AND b.phone = selected.phone
       AND b.legacy_member_no = selected.primary_card_no
     WHERE b.bind_status = 'BOUND'
), legacy_orders AS (
    SELECT o.*,
           selected.phone AS selected_phone
      FROM park_order o
      JOIN selected_member selected
        ON o.context_payload ->> 'legacyMemberNo' = selected.primary_card_no
     WHERE o.deleted = FALSE
       AND o.app_id = 'LEGACY_IMPORT'
       AND o.context_payload ->> 'legacyImported' = 'true'
), wrong_gift_records AS (
    SELECT coupon_nos
      FROM admin_marketing_new_user_gift_record
     WHERE member_no = '{member_no}'
       AND deleted = FALSE
), wrong_gift_coupon_numbers AS (
    SELECT DISTINCT jsonb_array_elements_text(COALESCE(coupon_nos, '[]'::jsonb)) AS coupon_no
      FROM wrong_gift_records
)
SELECT jsonb_build_object(
    'memberNo', '{member_no}',
    'profileExists', EXISTS (SELECT 1 FROM selected_member),
    'legacySource', COALESCE((SELECT source_channel = 'legacyImport' FROM selected_member), FALSE),
    'phonePresent', COALESCE((SELECT NULLIF(phone, '') IS NOT NULL FROM selected_member), FALSE),
    'primaryCardPresent', COALESCE((SELECT NULLIF(primary_card_no, '') IS NOT NULL FROM selected_member), FALSE),
    'miniProgramBound', COALESCE((
        SELECT app_id <> 'LEGACY_IMPORT'
           AND external_user_id IS NOT NULL
           AND external_user_id NOT LIKE 'LEGACY:%'
          FROM selected_member
    ), FALSE),
    'activePhoneProfileCount', COALESCE((SELECT profile_count FROM matching_profiles), 0),
    'boundIdentityProfileCount', COALESCE((SELECT profile_count FROM bound_identity_profiles), 0),
    'legacyBindCount', COALESCE((SELECT bind_count FROM legacy_bind), 0),
    'legacyOrderCount', (SELECT COUNT(*) FROM legacy_orders),
    'legacyPhoneScopedOrderCount', (
        SELECT COUNT(*)
          FROM legacy_orders
         WHERE NULLIF(selected_phone, '') IS NOT NULL
           AND contact_phone = selected_phone
    ),
    'legacyCompletedOrderCount', (
        SELECT COUNT(*)
          FROM legacy_orders
         WHERE order_status IN ('FULFILLED', 'USED', 'COMPLETED')
    ),
    'legacyVisibleCompletedOrderCount', (
        SELECT COUNT(*)
          FROM legacy_orders
         WHERE order_status IN ('FULFILLED', 'USED', 'COMPLETED')
           AND NULLIF(selected_phone, '') IS NOT NULL
           AND contact_phone = selected_phone
    ),
    'newUserGiftRecordCount', (SELECT COUNT(*) FROM wrong_gift_records),
    'newUserGiftCrmCouponCount', (
        SELECT COUNT(*)
          FROM crm_member_coupon_instance c
         WHERE c.member_no = '{member_no}'
           AND c.deleted = FALSE
           AND c.coupon_instance_no IN (SELECT coupon_no FROM wrong_gift_coupon_numbers)
    ),
    'newUserGiftPromotionCouponCount', (
        SELECT COUNT(*)
          FROM promotion_member_coupon c
         WHERE c.user_id = (SELECT external_user_id FROM selected_member)
           AND c.coupon_no IN (SELECT coupon_no FROM wrong_gift_coupon_numbers)
    )
)
"""
    raw = psql_scalar(sql)
    report = json.loads(raw)
    checks = {
        "profileExists": report.get("profileExists") is True,
        "legacySource": report.get("legacySource") is True,
        "phonePresent": report.get("phonePresent") is True,
        "primaryCardPresent": report.get("primaryCardPresent") is True,
        "miniProgramBound": report.get("miniProgramBound") is True,
        "activePhoneProfileCount": report.get("activePhoneProfileCount") == 1,
        "boundIdentityProfileCount": report.get("boundIdentityProfileCount") == 1,
        "legacyBindCount": report.get("legacyBindCount") == 1,
        "legacyOrderCount": (report.get("legacyOrderCount") or 0) > 0,
        "legacyPhoneScopedOrderCount": report.get("legacyPhoneScopedOrderCount") == report.get("legacyOrderCount"),
        "legacyCompletedOrderCount": (report.get("legacyCompletedOrderCount") or 0) > 0,
        "legacyVisibleCompletedOrderCount": (
            report.get("legacyVisibleCompletedOrderCount") == report.get("legacyCompletedOrderCount")
        ),
        "newUserGiftRecordCount": report.get("newUserGiftRecordCount") == 0,
        "newUserGiftCrmCouponCount": report.get("newUserGiftCrmCouponCount") == 0,
        "newUserGiftPromotionCouponCount": report.get("newUserGiftPromotionCouponCount") == 0,
    }
    report["verifiedAt"] = dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")
    report["checks"] = checks
    report["verification"] = "passed" if all(checks.values()) else "failed"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["verification"] != "passed":
        raise SystemExit("legacy member binding verification failed")


def sql_without_transaction(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    begin_count = sum(line.strip() == "BEGIN;" for line in lines)
    commit_count = sum(line.strip() == "COMMIT;" for line in lines)
    if begin_count != 1 or commit_count != 1:
        raise SystemExit(f"expected exactly one BEGIN/COMMIT pair in {path}")
    return "\n".join(line for line in lines if line.strip() not in {"BEGIN;", "COMMIT;"})


def psql_meta_quote(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise SystemExit("artifact path contains a newline")
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def precommit_verification_sql(member_summary: dict, order_summary: dict) -> str:
    expected = expected_verification(member_summary, order_summary)
    checks = {
        "crm_member_profile": "SELECT COUNT(*) FROM public.crm_member_profile",
        "crm_member_stat": "SELECT COUNT(*) FROM public.crm_member_stat",
        "crm_legacy_member_bind": "SELECT COUNT(*) FROM public.crm_legacy_member_bind",
        "admin_member_growth_record": "SELECT COUNT(*) FROM public.admin_member_growth_record",
        "park_order": "SELECT COUNT(*) FROM public.park_order",
        "park_order_item": "SELECT COUNT(*) FROM public.park_order_item",
        "park_order_status_event": "SELECT COUNT(*) FROM public.park_order_status_event",
        "points_balance": "SELECT COALESCE(SUM(points_balance), 0) FROM public.crm_member_profile",
        "order_count": "SELECT COALESCE(SUM(order_count), 0) FROM public.crm_member_profile",
        "paid_amount_cent": "SELECT COALESCE(SUM(paid_amount_cent), 0) FROM public.crm_member_profile",
        "park_order_payable_amount_cent": "SELECT COALESCE(SUM(payable_amount_cent), 0) FROM public.park_order",
        "park_order_item_amount_cent": "SELECT COALESCE(SUM(amount_cent), 0) FROM public.park_order_item",
        "principal_balance_cent": "SELECT COALESCE(SUM(principal_balance_cent), 0) FROM public.crm_member_profile",
        "gift_balance_cent": "SELECT COALESCE(SUM(gift_balance_cent), 0) FROM public.crm_member_profile",
        "card_balance_cent": "SELECT COALESCE(SUM(card_balance_cent), 0) FROM public.crm_member_profile",
        "frozen_balance_cent": "SELECT COALESCE(SUM(frozen_balance_cent), 0) FROM public.crm_member_profile",
    }
    statements = []
    for name, query in checks.items():
        statements.append(
            f"IF ({query}) <> {int(expected[name])} THEN "
            f"RAISE EXCEPTION 'precommit verification failed: {name}'; END IF;"
        )
    allowed_non_zero = {
        "admin_member_growth_record",
        "crm_legacy_member_bind",
        "crm_member_stat",
        "crm_member_profile",
        "park_order",
        "park_order_item",
        "park_order_status_event",
    }
    for table in all_tables():
        if table not in allowed_non_zero:
            statements.append(
                f"IF (SELECT COUNT(*) FROM public.{table}) <> 0 THEN "
                f"RAISE EXCEPTION 'precommit residual rows: {table}'; END IF;"
            )
    return "DO $$ BEGIN\n  " + "\n  ".join(statements) + "\nEND $$;"


def atomic_import_sql(artifact_dir: Path, member_summary: dict, order_summary: dict) -> str:
    member_sql = artifact_dir / "load_import.sql"
    order_sql = artifact_dir / "orders" / "load_import.sql"
    return "\n".join([
        r"\set ON_ERROR_STOP on",
        "BEGIN;",
        r"\cd " + psql_meta_quote(str(member_sql.parent.resolve())),
        sql_without_transaction(member_sql),
        r"\cd " + psql_meta_quote(str(order_sql.parent.resolve())),
        sql_without_transaction(order_sql),
        precommit_verification_sql(member_summary, order_summary),
        "COMMIT;",
        "",
    ])


def import_artifacts(artifact_dir: Path, state_file: Path, confirmation: str) -> None:
    if confirmation != IMPORT_CONFIRMATION:
        raise SystemExit(f"import requires --confirm {IMPORT_CONFIRMATION}")
    state = require_frozen_state(state_file)
    if state.get("phase") == "import_in_progress":
        interrupted_counts = inventory()
        if all(count == 0 for count in interrupted_counts.values()):
            write_freeze_state(
                state_file,
                state,
                phase="cleaned",
                import_rolled_back_at=(
                    dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")
                ),
            )
        else:
            raise SystemExit("interrupted import left rows; run verify before any retry")
    if state.get("phase") != "cleaned":
        raise SystemExit(f"import requires cleaned phase; current phase={state.get('phase')}")
    member_summary, order_summary = validate_artifacts(artifact_dir)
    residuals = {table: count for table, count in inventory().items() if count != 0}
    if residuals:
        raise SystemExit(f"database is not clean; import blocked: {residuals}")
    write_freeze_state(
        state_file,
        state,
        phase="import_in_progress",
        import_started_at=dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
    )
    try:
        psql_script(atomic_import_sql(artifact_dir, member_summary, order_summary))
    except BaseException:
        try:
            rollback_counts = inventory()
            if all(count == 0 for count in rollback_counts.values()):
                write_freeze_state(
                    state_file,
                    state,
                    phase="cleaned",
                    import_rolled_back_at=(
                        dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")
                    ),
                )
        except Exception:
            pass
        raise
    write_freeze_state(
        state_file,
        state,
        phase="imported_unverified",
        data_mutated=True,
        imported_at=dt.datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" "),
    )
    verify(artifact_dir, state_file)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--state-file", required=True, type=Path)
    freeze_parser.add_argument("--confirm", required=True)

    unfreeze_parser = subparsers.add_parser("unfreeze")
    unfreeze_parser.add_argument("--state-file", required=True, type=Path)
    unfreeze_parser.add_argument("--artifacts", type=Path)
    unfreeze_parser.add_argument("--confirm", required=True)

    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--out", type=Path)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--out", required=True, type=Path)
    backup_parser.add_argument("--state-file", required=True, type=Path)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--backup-dir", required=True, type=Path)
    cleanup_parser.add_argument("--state-file", required=True, type=Path)
    cleanup_parser.add_argument("--confirm", required=True)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--artifacts", required=True, type=Path)
    import_parser.add_argument("--state-file", required=True, type=Path)
    import_parser.add_argument("--confirm", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--artifacts", required=True, type=Path)
    verify_parser.add_argument("--state-file", type=Path)

    binding_parser = subparsers.add_parser("verify-legacy-member-binding")
    binding_parser.add_argument("--member-no", required=True)
    binding_parser.add_argument("--out", type=Path)

    args = parser.parse_args(argv)
    if args.command == "freeze":
        freeze_writes(args.state_file, args.confirm)
    elif args.command == "unfreeze":
        unfreeze_writes(args.state_file, args.confirm, args.artifacts)
    elif args.command == "inventory":
        counts = inventory()
        if args.out:
            write_counts(args.out, counts)
        print(json.dumps(counts, ensure_ascii=False, indent=2))
    elif args.command == "backup":
        backup(args.out, args.state_file)
    elif args.command == "cleanup":
        cleanup(args.backup_dir, args.state_file, args.confirm)
    elif args.command == "import":
        import_artifacts(args.artifacts, args.state_file, args.confirm)
    elif args.command == "verify":
        verify(args.artifacts, args.state_file)
    elif args.command == "verify-legacy-member-binding":
        verify_legacy_member_binding(args.member_no, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
