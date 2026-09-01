#!/usr/bin/env python3
"""Convert HelloKitty old-system member Excel exports into CRM import artifacts.

This script intentionally depends only on the Python standard library so it can
run on cutover day without installing spreadsheet packages.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

EXPECTED_HEADERS = {
    "members": ["编号", "姓名", "昵称", "性别", "生日", "手机号", "注册时间", "积分余额", "等级"],
    "orders": ["订单编号", "会员编号", "订单金额", "订单状态", "店铺名称", "订单日期"],
    "accounts": ["会员编号", "账户类型", "状态", "开始时间", "结束时间", "实际余额", "可用余额"],
}

MEMBER_HEADER_LAYOUTS = [
    EXPECTED_HEADERS["members"],
    ["会员编号", "姓名", "昵称", "性别", "生日", "手机号", "注册时间", "积分余额", "会员等级"],
]
MEMBER_FIELD_NAMES = MEMBER_HEADER_LAYOUTS[1]

ACCOUNT_HEADER_LAYOUTS = {
    "legacy_account_export": {
        "headers": ["会员编号", "账户类型", "状态", "开始时间", "结束时间", "实际余额", "可用余额"],
        "member_no": 0,
        "account_type": 1,
        "status": 2,
        "start_at": 3,
        "end_at": 4,
        "actual_balance": 5,
        "available_balance": 6,
    },
    "kcoin_account_export": {
        "headers": ["账户编号", "STATUS_ID", "账户类型", "会员编号", "姓名", "开始日期", "截止日期", "实际余额", "可用余额"],
        "member_no": 3,
        "account_type": 2,
        "status": 1,
        "start_at": 5,
        "end_at": 6,
        "actual_balance": 7,
        "available_balance": 8,
    },
}

VALID_ORDER_STATUSES = {"已完成", "已确认", "已审核"}
LEVEL_MAP = {"初级会员": "L1", "中级会员": "L2", "高级会员": "L3"}
GENDER_MAP = {"M": "MALE", "男": "MALE", "F": "FEMALE", "女": "FEMALE"}
MOBILE_RE = re.compile(r"^1\d{10}$")
CELL_CONTROL_RE = re.compile(r"[\r\n\t]+")
KCOIN_IMPORTED_ACCOUNT_TYPE = "卡币账户"
MEMBER_DUPLICATE_POLICY = "last_occurrence_wins"
ACCOUNT_TYPES_EXCLUDED_FROM_IMPORT = {"公益账户"}

PROFILE_COLUMNS = [
    "member_no",
    "platform",
    "app_id",
    "external_user_id",
    "nick_name",
    "avatar_url",
    "phone_country_code",
    "phone",
    "id_card_no",
    "birthday",
    "gender",
    "region_code",
    "region_name",
    "car_plate_no",
    "online_store_url",
    "level_code",
    "growth_value",
    "status",
    "member_type",
    "email",
    "address",
    "id_card_type",
    "birthday_updated_at",
    "source_channel",
    "join_store_id",
    "join_store_name",
    "first_card_brand_name",
    "remark",
    "points_balance",
    "pending_points",
    "expiring_points",
    "points_expire_at",
    "order_count",
    "paid_amount_cent",
    "card_balance_cent",
    "principal_balance_cent",
    "gift_balance_cent",
    "frozen_balance_cent",
    "member_tags",
    "segment_tags",
    "risk_flags",
    "blacklist_flag",
    "last_visit_at",
    "last_order_at",
    "registered_at",
    "member_scheme_id",
    "member_scheme_name",
    "primary_card_no",
    "created_at",
    "updated_at",
    "deleted",
    "version",
]

STAT_COLUMNS = [
    "member_no",
    "favorite_count",
    "coupon_count",
    "distribution_amount_cent",
    "created_at",
    "updated_at",
    "version",
]

BIND_COLUMNS = [
    "member_no",
    "phone",
    "legacy_member_no",
    "bind_status",
    "created_at",
    "updated_at",
    "version",
]

GROWTH_COLUMNS = [
    "record_id",
    "member_no",
    "biz_type",
    "biz_no",
    "title",
    "growth_value",
    "points_value",
    "change_type",
    "points_status",
    "balance_after",
    "expire_at",
    "store_name",
    "operator_name",
    "pos_terminal_id",
    "occurred_at",
    "remark",
    "deleted",
    "created_at",
    "updated_at",
    "version",
]


def col_to_idx(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + ord(ch.upper()) - 64
    return value - 1


def load_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for si in root.findall("a:si", NS):
        values.append("".join((t.text or "") for t in si.findall(".//a:t", NS)))
    return values


def first_sheet_path(zf: ZipFile) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheet = workbook.find("a:sheets", NS)[0]
    rel_id = sheet.attrib[f"{{{NS['r']}}}id"]
    target = rel_map[rel_id]
    return "xl/" + target.lstrip("/") if not target.startswith("xl/") else target


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value = cell.find("a:v", NS)
        if value is None or value.text is None:
            return ""
        return shared_strings[int(value.text)]
    if cell_type == "inlineStr":
        return "".join((t.text or "") for t in cell.findall(".//a:t", NS))
    value = cell.find("a:v", NS)
    return value.text if value is not None and value.text is not None else ""


def iter_xlsx_rows(path: Path):
    with ZipFile(path) as zf:
        shared_strings = load_shared_strings(zf)
        sheet_path = first_sheet_path(zf)
        for _, elem in ET.iterparse(zf.open(sheet_path), events=("end",)):
            if elem.tag.endswith("}row"):
                values: list[str] = []
                for cell in elem.findall("a:c", NS):
                    idx = col_to_idx(cell.attrib.get("r", "A1"))
                    while len(values) <= idx:
                        values.append("")
                    values[idx] = cell_value(cell, shared_strings).strip()
                yield values
                elem.clear()


def normalize_header(row: list[str]) -> list[str]:
    return [clean_cell_text(item) for item in row]


def require_header(kind: str, row: list[str]) -> None:
    expected_layouts = MEMBER_HEADER_LAYOUTS if kind == "members" else [EXPECTED_HEADERS[kind]]
    actual = normalize_header(row)
    if any(actual[: len(expected)] == expected for expected in expected_layouts):
        return
    raise SystemExit(f"{kind} header mismatch: expected one of={expected_layouts}, actual={actual}")


def resolve_account_columns(row: list[str]) -> tuple[str, dict[str, int]]:
    actual = normalize_header(row)
    for layout_name, layout in ACCOUNT_HEADER_LAYOUTS.items():
        expected = layout["headers"]
        if actual[: len(expected)] == expected:
            return layout_name, {key: value for key, value in layout.items() if key != "headers"}
    expected_layouts = [layout["headers"] for layout in ACCOUNT_HEADER_LAYOUTS.values()]
    raise SystemExit(f"accounts header mismatch: expected one of={expected_layouts}, actual={actual}")


def text(row: list[str], idx: int) -> str:
    return clean_cell_text(row[idx]) if idx < len(row) and row[idx] is not None else ""


def clean_cell_text(raw: str) -> str:
    return CELL_CONTROL_RE.sub(" ", raw or "").strip()


def parse_decimal(raw: str) -> Decimal:
    raw = (raw or "").strip().replace(",", "")
    if raw == "":
        return Decimal("0")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def to_int_string(value: Decimal) -> str:
    return str(int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def money_to_cent(raw: str) -> int:
    cents = parse_decimal(raw) * Decimal("100")
    return int(cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cent_to_yuan_text(cents: int) -> str:
    return str((Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def excel_datetime(raw: str) -> str:
    raw = (raw or "").strip()
    if raw == "":
        return ""
    try:
        serial = Decimal(raw)
    except InvalidOperation:
        return raw
    base = dt.datetime(1899, 12, 30)
    days = int(serial)
    fraction = serial - days
    seconds = int((fraction * Decimal(86400)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    value = base + dt.timedelta(days=days, seconds=seconds)
    return value.replace(microsecond=0).isoformat(sep=" ")


def excel_date(raw: str) -> str:
    value = excel_datetime(raw)
    return value[:10] if value else ""


def member_no(old_member_no: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", old_member_no.strip())
    return f"LEGACY_{normalized}"[:64]


def valid_phone(phone: str) -> bool:
    return bool(MOBILE_RE.fullmatch(phone or ""))


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_csv(path: Path, columns: list[str], rows) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
            count += 1
    return count


def select_last_member_rows(path: Path) -> tuple[dict[str, int], dict[str, list[int]], dict]:
    rows = iter_xlsx_rows(path)
    require_header("members", next(rows))
    last_rows: dict[str, int] = {}
    duplicate_member_rows: dict[str, list[int]] = {}
    source_rows = 0
    empty_member_no_rows = 0
    for row_no, row in enumerate(rows, start=2):
        source_rows += 1
        old_no = text(row, 0)
        if not old_no:
            empty_member_no_rows += 1
            continue
        if old_no in last_rows:
            duplicate_member_rows.setdefault(old_no, [last_rows[old_no]]).append(row_no)
        last_rows[old_no] = row_no
    return last_rows, duplicate_member_rows, {
        "source_rows": source_rows,
        "selected_rows": len(last_rows),
        "duplicate_member_ids": len(duplicate_member_rows),
        "duplicate_rows_dropped": source_rows - empty_member_no_rows - len(last_rows),
        "empty_member_no_rows": empty_member_no_rows,
        "deduplication_policy": MEMBER_DUPLICATE_POLICY,
    }


def audit_duplicate_member_rows(
        selected_member_rows: dict[str, int],
        duplicate_values: dict[str, list[tuple[int, list[str]]]],
        issues: list[dict],
) -> dict[str, int]:
    counts = {
        "exact_duplicate_rows": 0,
        "points_conflict_duplicate_rows": 0,
        "field_conflict_duplicate_rows": 0,
    }
    for old_no, snapshots in duplicate_values.items():
        selected_row_no = selected_member_rows[old_no]
        selected_values = next(values for row_no, values in snapshots if row_no == selected_row_no)
        for row_no, values in snapshots:
            if row_no == selected_row_no:
                continue
            differing_indexes = [idx for idx, value in enumerate(values) if value != selected_values[idx]]
            if not differing_indexes:
                counts["exact_duplicate_rows"] += 1
                issues.append({
                    "source": "members",
                    "row": row_no,
                    "severity": "INFO",
                    "code": "MEMBER_NO_DUPLICATE_EXACT_LAST_WINS",
                    "message": f"{old_no}: dropped_row={row_no}, selected_row={selected_row_no}",
                })
            elif differing_indexes == [7]:
                counts["points_conflict_duplicate_rows"] += 1
                issues.append({
                    "source": "members",
                    "row": row_no,
                    "severity": "WARN",
                    "code": "MEMBER_NO_DUPLICATE_POINTS_LAST_WINS",
                    "message": (
                        f"{old_no}: dropped_row={row_no}, selected_row={selected_row_no}, "
                        f"points={values[7]}->{selected_values[7]}"
                    ),
                })
            else:
                counts["field_conflict_duplicate_rows"] += 1
                differing_fields = [MEMBER_FIELD_NAMES[idx] for idx in differing_indexes]
                issues.append({
                    "source": "members",
                    "row": row_no,
                    "severity": "ERROR",
                    "code": "MEMBER_NO_DUPLICATE_FIELD_CONFLICT",
                    "message": (
                        f"{old_no}: dropped_row={row_no}, selected_row={selected_row_no}, "
                        f"differing_fields={','.join(differing_fields)}"
                    ),
                })
    return counts


def load_members(path: Path, issues: list[dict]) -> tuple[dict[str, dict], dict]:
    selected_member_rows, duplicate_member_rows, member_summary = select_last_member_rows(path)
    rows = iter_xlsx_rows(path)
    require_header("members", next(rows))
    members: dict[str, dict] = {}
    phone_seen: dict[str, str] = {}
    duplicate_values: dict[str, list[tuple[int, list[str]]]] = {}
    for row_no, row in enumerate(rows, start=2):
        old_no = text(row, 0)
        if not old_no:
            issues.append({"source": "members", "row": row_no, "severity": "ERROR", "code": "MEMBER_NO_EMPTY", "message": "会员编号为空"})
            continue
        if old_no in duplicate_member_rows:
            duplicate_values.setdefault(old_no, []).append((row_no, [text(row, idx) for idx in range(9)]))
        if selected_member_rows.get(old_no) != row_no:
            continue
        name = text(row, 1)
        nickname = text(row, 2)
        gender_raw = text(row, 3)
        raw_phone = text(row, 5)
        phone = raw_phone if valid_phone(raw_phone) else ""
        if raw_phone and not phone:
            issues.append({"source": "members", "row": row_no, "severity": "WARN", "code": "PHONE_INVALID", "message": f"{old_no}:{raw_phone}"})
        if phone and phone in phone_seen:
            issues.append({"source": "members", "row": row_no, "severity": "WARN", "code": "PHONE_DUPLICATE", "message": f"{phone}: first={phone_seen[phone]}, current={old_no}"})
            phone = ""
        elif phone:
            phone_seen[phone] = old_no
        points = parse_decimal(text(row, 7))
        registered_at = excel_datetime(text(row, 6))
        members[old_no] = {
            "legacy_member_no": old_no,
            "member_no": member_no(old_no),
            "name": name,
            "nick_name": nickname or name or "老会员",
            "gender": GENDER_MAP.get(gender_raw, "UNKNOWN"),
            "birthday": excel_date(text(row, 4)),
            "phone": phone,
            "registered_at": registered_at,
            "points": int(points.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            "level_code": LEVEL_MAP.get(text(row, 8), "L1"),
            "raw_level": text(row, 8),
            "order_count": 0,
            "paid_amount_cent": 0,
            "last_order_at": "",
            "principal_balance_cent": 0,
            "gift_balance_cent": 0,
            "card_coin_balance_cent": 0,
            "frozen_balance_cent": 0,
            "other_balance_cent": 0,
        }
    member_summary.update(audit_duplicate_member_rows(selected_member_rows, duplicate_values, issues))
    return members, member_summary


def apply_orders(path: Path, members: dict[str, dict], issues: list[dict]) -> dict:
    rows = iter_xlsx_rows(path)
    require_header("orders", next(rows))
    status_counts: dict[str, int] = {}
    store_counts: dict[str, int] = {}
    missing_refs = 0
    total_rows = 0
    valid_rows = 0
    valid_amount_cent = 0
    for row_no, row in enumerate(rows, start=2):
        total_rows += 1
        order_no = text(row, 0)
        old_no = text(row, 1)
        status = text(row, 3)
        store = text(row, 4)
        status_counts[status] = status_counts.get(status, 0) + 1
        store_counts[store] = store_counts.get(store, 0) + 1
        if old_no not in members:
            missing_refs += 1
            if missing_refs <= 100:
                issues.append({"source": "orders", "row": row_no, "severity": "WARN", "code": "ORDER_MEMBER_MISSING", "message": f"{order_no}:{old_no}"})
            continue
        if status in VALID_ORDER_STATUSES:
            amount_cent = money_to_cent(text(row, 2))
            order_at = excel_datetime(text(row, 5))
            member = members[old_no]
            member["order_count"] += 1
            member["paid_amount_cent"] += amount_cent
            valid_rows += 1
            valid_amount_cent += amount_cent
            if order_at and (not member["last_order_at"] or order_at > member["last_order_at"]):
                member["last_order_at"] = order_at
    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "valid_amount_cent": valid_amount_cent,
        "missing_member_refs": missing_refs,
        "status_counts": status_counts,
        "top_stores": sorted(store_counts.items(), key=lambda item: item[1], reverse=True)[:20],
    }


def apply_accounts(path: Path, members: dict[str, dict], issues: list[dict]) -> tuple[dict, list[dict]]:
    rows = iter_xlsx_rows(path)
    layout_name, columns = resolve_account_columns(next(rows))
    total_rows = 0
    missing_refs = 0
    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    amount_totals: dict[str, dict] = {}
    imported_rows = 0
    excluded_type_counts: dict[str, int] = {}
    detail_rows: list[dict] = []
    for row_no, row in enumerate(rows, start=2):
        total_rows += 1
        old_no = text(row, columns["member_no"])
        account_type = text(row, columns["account_type"])
        status = text(row, columns["status"])
        start_at = excel_datetime(text(row, columns["start_at"]))
        end_at = excel_datetime(text(row, columns["end_at"]))
        actual_cent = money_to_cent(text(row, columns["actual_balance"]))
        available_cent = money_to_cent(text(row, columns["available_balance"]))
        type_counts[account_type] = type_counts.get(account_type, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        amount_key = f"{account_type}|{status}"
        amount_total = amount_totals.setdefault(amount_key, {"count": 0, "actual_balance_cent": 0, "available_balance_cent": 0})
        amount_total["count"] += 1
        amount_total["actual_balance_cent"] += actual_cent
        amount_total["available_balance_cent"] += available_cent
        excluded = account_type in ACCOUNT_TYPES_EXCLUDED_FROM_IMPORT
        if layout_name == "kcoin_account_export" and account_type != KCOIN_IMPORTED_ACCOUNT_TYPE:
            excluded = True
        if excluded:
            excluded_type_counts[account_type] = excluded_type_counts.get(account_type, 0) + 1
            continue
        imported_rows += 1
        detail_rows.append({
            "legacy_member_no": old_no,
            "member_no": member_no(old_no) if old_no in members else "",
            "account_type": account_type,
            "status": status,
            "start_at": start_at,
            "end_at": end_at,
            "actual_balance_cent": actual_cent,
            "available_balance_cent": available_cent,
        })
        if old_no not in members:
            missing_refs += 1
            issues.append({"source": "accounts", "row": row_no, "severity": "WARN", "code": "ACCOUNT_MEMBER_MISSING", "message": old_no})
            continue
        member = members[old_no]
        if status == "冻结":
            member["frozen_balance_cent"] += available_cent
            continue
        if status not in {"有效", "取消"}:
            issues.append({"source": "accounts", "row": row_no, "severity": "WARN", "code": "ACCOUNT_STATUS_UNKNOWN", "message": f"{old_no}:{status}"})
        if status != "有效":
            continue
        if account_type == "储蓄账户":
            member["principal_balance_cent"] += available_cent
        elif account_type == "活动币账户":
            member["gift_balance_cent"] += available_cent
        elif account_type == "卡币账户":
            member["card_coin_balance_cent"] += available_cent
        elif account_type == "公益账户":
            member["other_balance_cent"] += available_cent
        else:
            issues.append({"source": "accounts", "row": row_no, "severity": "WARN", "code": "ACCOUNT_TYPE_UNKNOWN", "message": f"{old_no}:{account_type}"})
    return {
        "source_layout": layout_name,
        "explicitly_excluded_account_types": sorted(ACCOUNT_TYPES_EXCLUDED_FROM_IMPORT),
        "total_rows": total_rows,
        "imported_rows": imported_rows,
        "excluded_rows": total_rows - imported_rows,
        "excluded_type_counts": excluded_type_counts,
        "missing_member_refs": missing_refs,
        "type_counts": type_counts,
        "status_counts": status_counts,
        "amount_totals": amount_totals,
    }, detail_rows


def profile_asset_summary(members: dict[str, dict]) -> dict:
    summary = {
        "points_balance": 0,
        "order_count": 0,
        "paid_amount_cent": 0,
        "principal_balance_cent": 0,
        "gift_balance_cent": 0,
        "card_coin_balance_cent": 0,
        "card_balance_cent": 0,
        "frozen_balance_cent": 0,
        "other_balance_cent": 0,
    }
    for member in members.values():
        summary["points_balance"] += member["points"]
        summary["order_count"] += member["order_count"]
        summary["paid_amount_cent"] += member["paid_amount_cent"]
        summary["principal_balance_cent"] += member["principal_balance_cent"]
        summary["gift_balance_cent"] += member["gift_balance_cent"]
        summary["card_coin_balance_cent"] += member["card_coin_balance_cent"]
        summary["card_balance_cent"] += member["principal_balance_cent"] + member["gift_balance_cent"] + member["card_coin_balance_cent"]
        summary["frozen_balance_cent"] += member["frozen_balance_cent"]
        summary["other_balance_cent"] += member["other_balance_cent"]
    return summary


def profile_rows(members: dict[str, dict], batch_code: str, import_time: str):
    for old_no, member in members.items():
        registered_at = member["registered_at"] or import_time
        principal = member["principal_balance_cent"]
        gift = member["gift_balance_cent"]
        card_coin = member["card_coin_balance_cent"]
        card_total = principal + gift + card_coin
        remark_parts = [f"老系统编号:{old_no}", f"导入批次:{batch_code}"]
        if member["name"]:
            remark_parts.insert(0, f"老系统姓名:{member['name']}")
        if member["raw_level"] and member["raw_level"] not in LEVEL_MAP:
            remark_parts.append(f"老系统等级:{member['raw_level']}")
        yield {
            "member_no": member["member_no"],
            "platform": "WECHAT",
            "app_id": "LEGACY_IMPORT",
            "external_user_id": f"LEGACY:{old_no}",
            "nick_name": member["nick_name"],
            "avatar_url": "",
            "phone_country_code": "86",
            "phone": member["phone"] if valid_phone(member["phone"]) else "",
            "id_card_no": "",
            "birthday": member["birthday"],
            "gender": member["gender"],
            "region_code": "",
            "region_name": "",
            "car_plate_no": "",
            "online_store_url": "",
            "level_code": member["level_code"],
            "growth_value": member["points"],
            "status": "ENABLED",
            "member_type": "member",
            "email": "",
            "address": "",
            "id_card_type": "",
            "birthday_updated_at": "",
            "source_channel": "legacyImport",
            "join_store_id": "",
            "join_store_name": "",
            "first_card_brand_name": "",
            "remark": ";".join(remark_parts)[:512],
            "points_balance": member["points"],
            "pending_points": "",
            "expiring_points": "",
            "points_expire_at": "",
            "order_count": member["order_count"],
            "paid_amount_cent": member["paid_amount_cent"],
            "card_balance_cent": card_total,
            "principal_balance_cent": principal,
            "gift_balance_cent": gift,
            "frozen_balance_cent": member["frozen_balance_cent"],
            "member_tags": json_text(["legacyImport"]),
            "segment_tags": json_text([]),
            "risk_flags": json_text([]),
            "blacklist_flag": "false",
            "last_visit_at": "",
            "last_order_at": member["last_order_at"],
            "registered_at": registered_at,
            "member_scheme_id": "",
            "member_scheme_name": "",
            "primary_card_no": old_no,
            "created_at": registered_at,
            "updated_at": import_time,
            "deleted": "false",
            "version": 0,
        }


def stat_rows(members: dict[str, dict], import_time: str):
    for member in members.values():
        yield {
            "member_no": member["member_no"],
            "favorite_count": 0,
            "coupon_count": 0,
            "distribution_amount_cent": 0,
            "created_at": import_time,
            "updated_at": import_time,
            "version": 0,
        }


def bind_rows(members: dict[str, dict], import_time: str):
    for old_no, member in members.items():
        if not valid_phone(member["phone"]):
            continue
        yield {
            "member_no": member["member_no"],
            "phone": member["phone"],
            "legacy_member_no": old_no,
            "bind_status": "BOUND",
            "created_at": import_time,
            "updated_at": import_time,
            "version": 0,
        }


def growth_rows(members: dict[str, dict], batch_code: str, import_time: str):
    for old_no, member in members.items():
        if member["points"] <= 0:
            continue
        occurred_at = member["registered_at"] or import_time
        yield {
            "record_id": f"LEGACY_POINTS_{old_no}"[:96],
            "member_no": member["member_no"],
            "biz_type": "LEGACY_IMPORT",
            "biz_no": batch_code,
            "title": "老系统积分导入",
            "growth_value": member["points"],
            "points_value": member["points"],
            "change_type": "increase",
            "points_status": "available",
            "balance_after": member["points"],
            "expire_at": "",
            "store_name": "",
            "operator_name": "legacy-import",
            "pos_terminal_id": "",
            "occurred_at": occurred_at,
            "remark": f"老系统会员编号:{old_no}",
            "deleted": "false",
            "created_at": import_time,
            "updated_at": import_time,
            "version": 0,
        }


def account_summary_rows(members: dict[str, dict]):
    for old_no, member in members.items():
        yield {
            "legacy_member_no": old_no,
            "member_no": member["member_no"],
            "principal_balance_cent": member["principal_balance_cent"],
            "gift_balance_cent": member["gift_balance_cent"],
            "card_coin_balance_cent": member["card_coin_balance_cent"],
            "card_balance_cent": member["principal_balance_cent"] + member["gift_balance_cent"] + member["card_coin_balance_cent"],
            "frozen_balance_cent": member["frozen_balance_cent"],
            "other_balance_cent": member["other_balance_cent"],
        }


def consumption_summary_rows(members: dict[str, dict]):
    for old_no, member in members.items():
        if member["order_count"] or member["paid_amount_cent"] or member["last_order_at"]:
            yield {
                "legacy_member_no": old_no,
                "member_no": member["member_no"],
                "order_count": member["order_count"],
                "paid_amount_cent": member["paid_amount_cent"],
                "last_order_at": member["last_order_at"],
            }


def write_load_sql(path: Path) -> None:
    path.write_text(
        """\\set ON_ERROR_STOP on
SET TIME ZONE 'Asia/Shanghai';
BEGIN;

CREATE TEMP TABLE tmp_legacy_crm_member_profile (LIKE crm_member_profile INCLUDING DEFAULTS);
\\copy tmp_legacy_crm_member_profile (member_no,platform,app_id,external_user_id,nick_name,avatar_url,phone_country_code,phone,id_card_no,birthday,gender,region_code,region_name,car_plate_no,online_store_url,level_code,growth_value,status,member_type,email,address,id_card_type,birthday_updated_at,source_channel,join_store_id,join_store_name,first_card_brand_name,remark,points_balance,pending_points,expiring_points,points_expire_at,order_count,paid_amount_cent,card_balance_cent,principal_balance_cent,gift_balance_cent,frozen_balance_cent,member_tags,segment_tags,risk_flags,blacklist_flag,last_visit_at,last_order_at,registered_at,member_scheme_id,member_scheme_name,primary_card_no,created_at,updated_at,deleted,version) FROM 'crm_member_profile.csv' WITH (FORMAT csv, HEADER true, NULL '');

INSERT INTO crm_member_profile (member_no,platform,app_id,external_user_id,nick_name,avatar_url,phone_country_code,phone,id_card_no,birthday,gender,region_code,region_name,car_plate_no,online_store_url,level_code,growth_value,status,member_type,email,address,id_card_type,birthday_updated_at,source_channel,join_store_id,join_store_name,first_card_brand_name,remark,points_balance,pending_points,expiring_points,points_expire_at,order_count,paid_amount_cent,card_balance_cent,principal_balance_cent,gift_balance_cent,frozen_balance_cent,member_tags,segment_tags,risk_flags,blacklist_flag,last_visit_at,last_order_at,registered_at,member_scheme_id,member_scheme_name,primary_card_no,created_at,updated_at,deleted,version)
SELECT member_no,platform,app_id,external_user_id,nick_name,avatar_url,phone_country_code,phone,id_card_no,birthday,gender,region_code,region_name,car_plate_no,online_store_url,level_code,growth_value,status,member_type,email,address,id_card_type,birthday_updated_at,source_channel,join_store_id,join_store_name,first_card_brand_name,remark,points_balance,pending_points,expiring_points,points_expire_at,order_count,paid_amount_cent,card_balance_cent,principal_balance_cent,gift_balance_cent,frozen_balance_cent,member_tags,segment_tags,risk_flags,blacklist_flag,last_visit_at,last_order_at,registered_at,member_scheme_id,member_scheme_name,primary_card_no,created_at,updated_at,deleted,version
FROM tmp_legacy_crm_member_profile
ON CONFLICT (member_no) DO UPDATE SET
  nick_name = EXCLUDED.nick_name,
  phone_country_code = EXCLUDED.phone_country_code,
  phone = EXCLUDED.phone,
  birthday = EXCLUDED.birthday,
  gender = EXCLUDED.gender,
  level_code = EXCLUDED.level_code,
  growth_value = EXCLUDED.growth_value,
  status = EXCLUDED.status,
  member_type = EXCLUDED.member_type,
  source_channel = EXCLUDED.source_channel,
  remark = EXCLUDED.remark,
  points_balance = EXCLUDED.points_balance,
  order_count = EXCLUDED.order_count,
  paid_amount_cent = EXCLUDED.paid_amount_cent,
  card_balance_cent = EXCLUDED.card_balance_cent,
  principal_balance_cent = EXCLUDED.principal_balance_cent,
  gift_balance_cent = EXCLUDED.gift_balance_cent,
  frozen_balance_cent = EXCLUDED.frozen_balance_cent,
  member_tags = EXCLUDED.member_tags,
  segment_tags = EXCLUDED.segment_tags,
  risk_flags = EXCLUDED.risk_flags,
  blacklist_flag = EXCLUDED.blacklist_flag,
  last_order_at = EXCLUDED.last_order_at,
  registered_at = EXCLUDED.registered_at,
  primary_card_no = EXCLUDED.primary_card_no,
  updated_at = EXCLUDED.updated_at,
  deleted = FALSE,
  version = crm_member_profile.version + 1;

CREATE TEMP TABLE tmp_legacy_crm_member_stat (LIKE crm_member_stat INCLUDING DEFAULTS);
\\copy tmp_legacy_crm_member_stat (member_no,favorite_count,coupon_count,distribution_amount_cent,created_at,updated_at,version) FROM 'crm_member_stat.csv' WITH (FORMAT csv, HEADER true, NULL '');

INSERT INTO crm_member_stat (member_no,favorite_count,coupon_count,distribution_amount_cent,created_at,updated_at,version)
SELECT member_no,favorite_count,coupon_count,distribution_amount_cent,created_at,updated_at,version
FROM tmp_legacy_crm_member_stat
ON CONFLICT (member_no) DO UPDATE SET
  updated_at = EXCLUDED.updated_at,
  version = crm_member_stat.version + 1;

CREATE TEMP TABLE tmp_legacy_member_bind (LIKE crm_legacy_member_bind INCLUDING DEFAULTS);
\\copy tmp_legacy_member_bind (member_no,phone,legacy_member_no,bind_status,created_at,updated_at,version) FROM 'crm_legacy_member_bind.csv' WITH (FORMAT csv, HEADER true, NULL '');

INSERT INTO crm_legacy_member_bind (member_no,phone,legacy_member_no,bind_status,created_at,updated_at,version)
SELECT member_no,phone,legacy_member_no,bind_status,created_at,updated_at,version
FROM tmp_legacy_member_bind
ON CONFLICT (member_no) DO UPDATE SET
  phone = EXCLUDED.phone,
  legacy_member_no = EXCLUDED.legacy_member_no,
  bind_status = EXCLUDED.bind_status,
  updated_at = EXCLUDED.updated_at,
  version = crm_legacy_member_bind.version + 1;

CREATE TEMP TABLE tmp_legacy_growth_record (LIKE admin_member_growth_record INCLUDING DEFAULTS);
\\copy tmp_legacy_growth_record (record_id,member_no,biz_type,biz_no,title,growth_value,points_value,change_type,points_status,balance_after,expire_at,store_name,operator_name,pos_terminal_id,occurred_at,remark,deleted,created_at,updated_at,version) FROM 'admin_member_growth_record.csv' WITH (FORMAT csv, HEADER true, NULL '');

INSERT INTO admin_member_growth_record (record_id,member_no,biz_type,biz_no,title,growth_value,points_value,change_type,points_status,balance_after,expire_at,store_name,operator_name,pos_terminal_id,occurred_at,remark,deleted,created_at,updated_at,version)
SELECT record_id,member_no,biz_type,biz_no,title,growth_value,points_value,change_type,points_status,balance_after,expire_at,store_name,operator_name,pos_terminal_id,occurred_at,remark,deleted,created_at,updated_at,version
FROM tmp_legacy_growth_record
ON CONFLICT (record_id) DO NOTHING;

COMMIT;
""",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--members", required=True, type=Path)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--accounts", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--batch-code", default="")
    args = parser.parse_args(argv)

    import_time = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    batch_code = args.batch_code or "LEGACY_MEMBER_IMPORT_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    args.out.mkdir(parents=True, exist_ok=True)

    issues: list[dict] = []
    members, member_summary = load_members(args.members, issues)
    order_summary = apply_orders(args.orders, members, issues)
    account_summary, account_details = apply_accounts(args.accounts, members, issues)
    profile_summary = profile_asset_summary(members)

    counts = {
        "crm_member_profile": write_csv(args.out / "crm_member_profile.csv", PROFILE_COLUMNS, profile_rows(members, batch_code, import_time)),
        "crm_member_stat": write_csv(args.out / "crm_member_stat.csv", STAT_COLUMNS, stat_rows(members, import_time)),
        "crm_legacy_member_bind": write_csv(args.out / "crm_legacy_member_bind.csv", BIND_COLUMNS, bind_rows(members, import_time)),
        "admin_member_growth_record": write_csv(args.out / "admin_member_growth_record.csv", GROWTH_COLUMNS, growth_rows(members, batch_code, import_time)),
        "legacy_account_summary": write_csv(
            args.out / "legacy_account_summary.csv",
            ["legacy_member_no", "member_no", "principal_balance_cent", "gift_balance_cent", "card_coin_balance_cent", "card_balance_cent", "frozen_balance_cent", "other_balance_cent"],
            account_summary_rows(members),
        ),
        "legacy_account_detail": write_csv(
            args.out / "legacy_account_detail.csv",
            ["legacy_member_no", "member_no", "account_type", "status", "start_at", "end_at", "actual_balance_cent", "available_balance_cent"],
            account_details,
        ),
        "legacy_consumption_summary": write_csv(
            args.out / "legacy_consumption_summary.csv",
            ["legacy_member_no", "member_no", "order_count", "paid_amount_cent", "last_order_at"],
            consumption_summary_rows(members),
        ),
        "validation_issues": write_csv(
            args.out / "validation_issues.csv",
            ["source", "row", "severity", "code", "message"],
            issues,
        ),
    }
    write_load_sql(args.out / "load_import.sql")

    summary = {
        "batch_code": batch_code,
        "generated_at": import_time,
        "counts": counts,
        "members": member_summary,
        "orders": order_summary,
        "accounts": account_summary,
        "profile_asset_summary": profile_summary,
        "issues_by_code": {},
        "output_dir": str(args.out),
    }
    for issue in issues:
        code = issue["code"]
        summary["issues_by_code"][code] = summary["issues_by_code"].get(code, 0) + 1
    (args.out / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 老会员迁移验证汇总",
        "",
        f"- 批次: `{batch_code}`",
        f"- 生成时间: `{import_time}`",
        f"- 输出目录: `{args.out}`",
        "",
        "## 输出行数",
    ]
    for key, value in counts.items():
        md.append(f"- `{key}`: {value}")
    md.extend(["", "## 会员去重"])
    md.append(f"- 原始会员行数: {member_summary['source_rows']}")
    md.append(f"- 选中会员行数: {member_summary['selected_rows']}")
    md.append(f"- 重复会员编号数: {member_summary['duplicate_member_ids']}")
    md.append(f"- 丢弃重复行数: {member_summary['duplicate_rows_dropped']}")
    md.append(f"- 完全相同重复行: {member_summary['exact_duplicate_rows']}")
    md.append(f"- 仅积分冲突重复行: {member_summary['points_conflict_duplicate_rows']}")
    md.append(f"- 其他字段冲突重复行: {member_summary['field_conflict_duplicate_rows']}")
    md.append(f"- 空会员编号行数: {member_summary['empty_member_no_rows']}")
    md.append(f"- 去重策略: `{member_summary['deduplication_policy']}`")
    md.extend(["", "## 订单汇总"])
    md.append(f"- 原始订单行数: {order_summary['total_rows']}")
    md.append(f"- 有效消费行数: {order_summary['valid_rows']}")
    md.append(f"- 有效消费金额: {cent_to_yuan_text(order_summary['valid_amount_cent'])} 元 / {order_summary['valid_amount_cent']} 分")
    md.append(f"- 订单会员缺失引用: {order_summary['missing_member_refs']}")
    md.extend(["", "## 账户汇总"])
    md.append(f"- 原始账户行数: {account_summary['total_rows']}")
    md.append(f"- 实际导入账户行数: {account_summary['imported_rows']}")
    md.append(f"- 排除账户行数: {account_summary['excluded_rows']}")
    md.append(f"- 明确排除账户类型: `{json_text(account_summary['explicitly_excluded_account_types'])}`")
    md.append(f"- 排除账户类型: `{json_text(account_summary['excluded_type_counts'])}`")
    md.append(f"- 账户会员缺失引用: {account_summary['missing_member_refs']}")
    md.append(f"- 账户类型: `{json_text(account_summary['type_counts'])}`")
    md.append(f"- 账户状态: `{json_text(account_summary['status_counts'])}`")
    md.append("")
    md.append("### 源账户金额汇总")
    for key, value in sorted(account_summary["amount_totals"].items()):
        md.append(
            f"- `{key}`: count={value['count']}, actual={cent_to_yuan_text(value['actual_balance_cent'])} 元, available={cent_to_yuan_text(value['available_balance_cent'])} 元"
        )
    md.append("")
    md.append("### 写入画像资产汇总")
    md.append(f"- 积分余额合计: {profile_summary['points_balance']}")
    md.append(f"- 订单数合计: {profile_summary['order_count']}")
    md.append(f"- 消费金额合计: {cent_to_yuan_text(profile_summary['paid_amount_cent'])} 元 / {profile_summary['paid_amount_cent']} 分")
    md.append(f"- 本金余额合计: {cent_to_yuan_text(profile_summary['principal_balance_cent'])} 元 / {profile_summary['principal_balance_cent']} 分")
    md.append(f"- 活动币余额合计: {cent_to_yuan_text(profile_summary['gift_balance_cent'])} 元 / {profile_summary['gift_balance_cent']} 分")
    md.append(f"- 卡币余额合计: {cent_to_yuan_text(profile_summary['card_coin_balance_cent'])} 元 / {profile_summary['card_coin_balance_cent']} 分")
    md.append(f"- 会员卡总余额合计: {cent_to_yuan_text(profile_summary['card_balance_cent'])} 元 / {profile_summary['card_balance_cent']} 分")
    md.append(f"- 冻结余额合计: {cent_to_yuan_text(profile_summary['frozen_balance_cent'])} 元 / {profile_summary['frozen_balance_cent']} 分")
    md.append(f"- 未写入画像的其他余额合计: {cent_to_yuan_text(profile_summary['other_balance_cent'])} 元 / {profile_summary['other_balance_cent']} 分")
    md.extend(["", "## 问题计数"])
    for key, value in sorted(summary["issues_by_code"].items()):
        md.append(f"- `{key}`: {value}")
    md.extend([
        "",
        "## 导入说明",
        "",
        "在目标数据库连接下，从本目录执行：",
        "",
        "```bash",
        "psql \"$DATABASE_URL\" -f load_import.sql",
        "```",
        "",
        "导入前请先人工复核 `validation_issues.csv` 和账户映射口径。",
    ])
    (args.out / "validation_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
