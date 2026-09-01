#!/usr/bin/env python3
"""Generate legacy consumption order import artifacts for HelloKitty UAT.

This script converts the old-system `消费记录.xlsx` into:
1. `park_order` import data so admin order center can query historical orders.
2. `park_order_item` import data for positive-amount rows.
3. `park_order_status_event` seed data for basic timeline visibility.
4. `crm_member_profile` summary corrections so `last_order_at` stays in Asia/Shanghai.

The implementation intentionally depends only on the Python standard library.
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

EXPECTED_HEADERS = ["订单编号", "会员编号", "订单金额", "订单状态", "店铺名称", "订单日期"]
VALID_COMPLETED_STATUSES = {"已完成", "已确认", "已审核"}
LOCAL_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
CELL_CONTROL_RE = re.compile(r"[\r\n\t]+")
NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
HOTEL_STORE_NAMES = {
    "安吉银润锦江城堡酒店",
    "银润小镇雷迪森维嘉酒店",
}

ORDER_COLUMNS = [
    "order_no",
    "legacy_member_no",
    "raw_amount_cent",
    "normalized_amount_cent",
    "include_item",
    "legacy_status",
    "order_status",
    "fulfillment_status",
    "refund_status",
    "store_name",
    "scene_type",
    "item_type",
    "item_name",
    "category_id",
    "business_channel",
    "payment_channel",
    "occurred_at",
    "paid_at",
    "canceled_at",
    "attributes",
]

ISSUE_COLUMNS = ["source", "row", "severity", "code", "message"]


def col_to_idx(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + ord(ch.upper()) - 64
    return value - 1


def clean_cell_text(raw: str) -> str:
    return CELL_CONTROL_RE.sub(" ", raw or "").strip()


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
                    values[idx] = clean_cell_text(cell_value(cell, shared_strings))
                yield values
                elem.clear()


def text(row: list[str], idx: int) -> str:
    return row[idx] if idx < len(row) else ""


def parse_decimal(raw: str) -> Decimal:
    raw = clean_cell_text(raw).replace(",", "")
    if raw == "":
        return Decimal("0")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def money_to_cent(raw: str) -> int:
    cents = parse_decimal(raw) * Decimal("100")
    return int(cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cent_to_yuan_text(cents: int) -> str:
    return str((Decimal(cents) / Decimal("100")).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))


def parse_local_datetime(raw: str) -> dt.datetime | None:
    value = clean_cell_text(raw)
    if value == "":
        return None
    if NUMERIC_RE.fullmatch(value):
        serial = Decimal(value)
        base = dt.datetime(1899, 12, 30)
        days = int(serial)
        fraction = serial - days
        microseconds = int((fraction * Decimal("86400000000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        naive = base + dt.timedelta(days=days, microseconds=microseconds)
        return naive.replace(tzinfo=LOCAL_TZ)
    for pattern in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
    ):
        try:
            naive = dt.datetime.strptime(value, pattern)
            if "H" not in pattern:
                naive = naive.replace(hour=0, minute=0, second=0)
            return naive.replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def format_timestamptz(value: dt.datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat(sep=" ", timespec="seconds")


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def normalize_store_name(store_name: str) -> str:
    return clean_cell_text(store_name) or "老系统消费"


def classify_scene_type(store_name: str) -> str:
    store_name = normalize_store_name(store_name)
    if store_name in HOTEL_STORE_NAMES:
        return "HOTEL"
    if "餐厅" in store_name or store_name == "外出":
        return "DINING"
    if "门票" in store_name or "年卡" in store_name or "兑换券" in store_name or "兑换点" in store_name:
        return "TICKET"
    return "MALL"


def classify_item_type(scene_type: str) -> str:
    if scene_type == "TICKET":
        return "TICKET"
    if scene_type == "DINING":
        return "DISH"
    if scene_type == "HOTEL":
        return "HOTEL_ROOM"
    return "SKU"


def classify_category_id(scene_type: str, store_name: str) -> str:
    if scene_type == "TICKET":
        return "legacy_ticket"
    if scene_type == "DINING":
        return "legacy_dining"
    if scene_type == "HOTEL":
        return "legacy_hotel"
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", normalize_store_name(store_name)).strip("_")
    return normalized[:64] if normalized else "legacy_mall"


def classify_business_channel(store_name: str) -> str:
    store_name = normalize_store_name(store_name)
    if "线上" in store_name or "兑换点" in store_name or store_name == "K币兑换专区":
        return "WECHAT_CHANNEL_LEGACY_IMPORT"
    return "OFFLINE_LEGACY_IMPORT"


def classify_payment_channel(business_channel: str) -> str:
    return "WECHAT" if "WECHAT_CHANNEL" in business_channel else "OFFLINE"


def map_order_lifecycle(legacy_status: str, occurred_at: dt.datetime, positive_amount: bool) -> dict[str, str]:
    if legacy_status in VALID_COMPLETED_STATUSES:
        return {
            "order_status": "FULFILLED",
            "fulfillment_status": "FULFILLED",
            "refund_status": "NONE",
            "paid_at": format_timestamptz(occurred_at if positive_amount or True else None),
            "canceled_at": "",
        }
    if legacy_status == "已取消":
        return {
            "order_status": "CANCELED",
            "fulfillment_status": "CANCELED",
            "refund_status": "NONE",
            "paid_at": "",
            "canceled_at": format_timestamptz(occurred_at),
        }
    if legacy_status == "已拒绝":
        return {
            "order_status": "CLOSED",
            "fulfillment_status": "FAILED",
            "refund_status": "NONE",
            "paid_at": "",
            "canceled_at": format_timestamptz(occurred_at),
        }
    return {
        "order_status": "PAID",
        "fulfillment_status": "NOT_STARTED",
        "refund_status": "NONE",
        "paid_at": format_timestamptz(occurred_at if positive_amount else None),
        "canceled_at": "",
    }


def load_orders(path: Path, issues: list[dict]) -> tuple[list[dict], dict]:
    rows = iter_xlsx_rows(path)
    header = next(rows)
    if [clean_cell_text(item) for item in header[: len(EXPECTED_HEADERS)]] != EXPECTED_HEADERS:
        raise SystemExit(f"orders header mismatch: expected={EXPECTED_HEADERS}, actual={header[:len(EXPECTED_HEADERS)]}")
    records: list[dict] = []
    order_seen: set[str] = set()
    status_counts: dict[str, int] = {}
    scene_counts: dict[str, int] = {}
    positive_count = 0
    header_only_count = 0
    positive_amount_cent = 0
    valid_positive_amount_cent = 0
    for row_no, row in enumerate(rows, start=2):
        order_no = text(row, 0)
        legacy_member_no = text(row, 1)
        legacy_status = text(row, 3)
        store_name = normalize_store_name(text(row, 4))
        occurred_at = parse_local_datetime(text(row, 5))
        if not order_no:
            issues.append({"source": "orders", "row": row_no, "severity": "ERROR", "code": "ORDER_NO_EMPTY", "message": "订单编号为空"})
            continue
        if order_no in order_seen:
            issues.append({"source": "orders", "row": row_no, "severity": "ERROR", "code": "ORDER_NO_DUPLICATE", "message": order_no})
            continue
        order_seen.add(order_no)
        if not legacy_member_no:
            issues.append({"source": "orders", "row": row_no, "severity": "WARN", "code": "LEGACY_MEMBER_NO_EMPTY", "message": order_no})
        if occurred_at is None:
            issues.append({"source": "orders", "row": row_no, "severity": "ERROR", "code": "ORDER_TIME_INVALID", "message": f"{order_no}:{text(row, 5)}"})
            continue
        amount_cent = money_to_cent(text(row, 2))
        positive_amount = amount_cent > 0
        normalized_amount_cent = amount_cent if amount_cent > 0 else 0
        scene_type = classify_scene_type(store_name)
        lifecycle = map_order_lifecycle(legacy_status, occurred_at, positive_amount)
        item_type = classify_item_type(scene_type)
        category_id = classify_category_id(scene_type, store_name)
        business_channel = classify_business_channel(store_name)
        payment_channel = classify_payment_channel(business_channel)
        include_item = positive_amount
        status_counts[legacy_status] = status_counts.get(legacy_status, 0) + 1
        scene_counts[scene_type] = scene_counts.get(scene_type, 0) + 1
        if include_item:
            positive_count += 1
            positive_amount_cent += normalized_amount_cent
        else:
            header_only_count += 1
        if legacy_status in VALID_COMPLETED_STATUSES and amount_cent > 0:
            valid_positive_amount_cent += amount_cent
        if legacy_status not in VALID_COMPLETED_STATUSES | {"已取消", "已拒绝", "待审核"}:
            issues.append({"source": "orders", "row": row_no, "severity": "WARN", "code": "ORDER_STATUS_UNMAPPED", "message": f"{order_no}:{legacy_status}"})
        attributes = {
            "skuName": store_name,
            "storeName": store_name,
            "legacyOrderNo": order_no,
            "legacyMemberNo": legacy_member_no,
            "legacyStatus": legacy_status,
            "legacyOccurredAt": format_timestamptz(occurred_at),
            "legacyAmountCent": amount_cent,
            "legacyImported": True,
            "sourceFile": "消费记录.xlsx",
            "imageUrl": "",
            "imageSrc": "",
        }
        records.append({
            "order_no": order_no,
            "legacy_member_no": legacy_member_no,
            "raw_amount_cent": amount_cent,
            "normalized_amount_cent": normalized_amount_cent,
            "include_item": "true" if include_item else "false",
            "legacy_status": legacy_status,
            "order_status": lifecycle["order_status"],
            "fulfillment_status": lifecycle["fulfillment_status"],
            "refund_status": lifecycle["refund_status"],
            "store_name": store_name,
            "scene_type": scene_type,
            "item_type": item_type,
            "item_name": store_name,
            "category_id": category_id,
            "business_channel": business_channel,
            "payment_channel": payment_channel,
            "occurred_at": format_timestamptz(occurred_at),
            "paid_at": lifecycle["paid_at"],
            "canceled_at": lifecycle["canceled_at"],
            "attributes": json_text(attributes),
        })
    return records, {
        "total_rows": len(records),
        "positive_item_rows": positive_count,
        "header_only_rows": header_only_count,
        "positive_amount_cent": positive_amount_cent,
        "valid_positive_amount_cent": valid_positive_amount_cent,
        "status_counts": status_counts,
        "scene_counts": scene_counts,
    }


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> int:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return len(rows)


def write_load_sql(path: Path) -> None:
    path.write_text(
        """\\set ON_ERROR_STOP on
SET TIME ZONE 'Asia/Shanghai';
BEGIN;

CREATE TEMP TABLE tmp_legacy_consumption_order (
    order_no VARCHAR(64) NOT NULL,
    legacy_member_no VARCHAR(64) NOT NULL,
    raw_amount_cent BIGINT NOT NULL,
    normalized_amount_cent BIGINT NOT NULL,
    include_item BOOLEAN NOT NULL,
    legacy_status VARCHAR(32) NOT NULL,
    order_status VARCHAR(32) NOT NULL,
    fulfillment_status VARCHAR(32) NOT NULL,
    refund_status VARCHAR(32) NOT NULL,
    store_name VARCHAR(128) NOT NULL,
    scene_type VARCHAR(32) NOT NULL,
    item_type VARCHAR(32) NOT NULL,
    item_name VARCHAR(256) NOT NULL,
    category_id VARCHAR(128),
    business_channel VARCHAR(64) NOT NULL,
    payment_channel VARCHAR(32) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    paid_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    attributes JSONB NOT NULL
);

\\copy tmp_legacy_consumption_order (order_no,legacy_member_no,raw_amount_cent,normalized_amount_cent,include_item,legacy_status,order_status,fulfillment_status,refund_status,store_name,scene_type,item_type,item_name,category_id,business_channel,payment_channel,occurred_at,paid_at,canceled_at,attributes) FROM 'legacy_consumption_orders.csv' WITH (FORMAT csv, HEADER true, NULL '');

WITH legacy_stats AS (
    SELECT legacy_member_no,
           COUNT(1) FILTER (WHERE legacy_status IN ('已完成', '已确认', '已审核')) AS order_count,
           COALESCE(SUM(CASE WHEN legacy_status IN ('已完成', '已确认', '已审核') THEN GREATEST(raw_amount_cent, 0) ELSE 0 END), 0) AS paid_amount_cent,
           MAX(occurred_at) FILTER (WHERE legacy_status IN ('已完成', '已确认', '已审核')) AS last_order_at
      FROM tmp_legacy_consumption_order
     GROUP BY legacy_member_no
)
UPDATE crm_member_profile p
   SET order_count = stats.order_count,
       paid_amount_cent = stats.paid_amount_cent,
       last_order_at = stats.last_order_at,
       updated_at = CURRENT_TIMESTAMP,
       version = p.version + 1
  FROM legacy_stats stats
 WHERE p.primary_card_no = stats.legacy_member_no
   AND p.deleted = FALSE
   AND (
       COALESCE(p.order_count, 0) <> COALESCE(stats.order_count, 0)
       OR COALESCE(p.paid_amount_cent, 0) <> COALESCE(stats.paid_amount_cent, 0)
       OR p.last_order_at IS DISTINCT FROM stats.last_order_at
   );

INSERT INTO park_order (
    order_no,
    user_id,
    platform,
    app_id,
    external_user_id,
    scene_type,
    order_status,
    payment_channel,
    channel,
    member_level,
    original_amount_cent,
    freight_amount_cent,
    discount_amount_cent,
    freight_discount_cent,
    payable_amount_cent,
    quote_snapshot_no,
    promotion_snapshot_no,
    selected_coupon_nos,
    context_payload,
    contact_name,
    contact_phone,
    remark,
    created_at,
    updated_at,
    paid_at,
    canceled_at,
    deleted,
    version,
    pay_no,
    fulfillment_status,
    refund_status
)
SELECT t.order_no,
       t.legacy_member_no AS user_id,
       'WECHAT' AS platform,
       'LEGACY_IMPORT' AS app_id,
       CONCAT('LEGACY:', t.legacy_member_no) AS external_user_id,
       t.scene_type,
       t.order_status,
       t.payment_channel,
       t.business_channel,
       COALESCE(NULLIF(p.level_code, ''), 'L1') AS member_level,
       t.normalized_amount_cent AS original_amount_cent,
       0 AS freight_amount_cent,
       0 AS discount_amount_cent,
       0 AS freight_discount_cent,
       t.normalized_amount_cent AS payable_amount_cent,
       NULL AS quote_snapshot_no,
       NULL AS promotion_snapshot_no,
       '[]'::jsonb AS selected_coupon_nos,
       jsonb_build_object(
           'legacyImported', TRUE,
           'legacyOrderNo', t.order_no,
           'legacyMemberNo', t.legacy_member_no,
           'legacyStatus', t.legacy_status,
           'legacyStoreName', t.store_name,
           'legacyOccurredAt', t.occurred_at,
           'legacyAmountCent', t.raw_amount_cent,
           'sourceFile', '消费记录.xlsx'
       ) AS context_payload,
       COALESCE(NULLIF(p.nick_name, ''), t.legacy_member_no) AS contact_name,
       COALESCE(NULLIF(p.phone, ''), '') AS contact_phone,
       '老系统消费记录导入' AS remark,
       t.occurred_at AS created_at,
       t.occurred_at AS updated_at,
       t.paid_at,
       t.canceled_at,
       FALSE AS deleted,
       0 AS version,
       NULL AS pay_no,
       t.fulfillment_status,
       t.refund_status
  FROM tmp_legacy_consumption_order t
  LEFT JOIN crm_member_profile p
    ON p.primary_card_no = t.legacy_member_no
   AND p.deleted = FALSE
ON CONFLICT (order_no) DO UPDATE
   SET user_id = EXCLUDED.user_id,
       platform = EXCLUDED.platform,
       app_id = EXCLUDED.app_id,
       external_user_id = EXCLUDED.external_user_id,
       scene_type = EXCLUDED.scene_type,
       order_status = EXCLUDED.order_status,
       payment_channel = EXCLUDED.payment_channel,
       channel = EXCLUDED.channel,
       member_level = EXCLUDED.member_level,
       original_amount_cent = EXCLUDED.original_amount_cent,
       freight_amount_cent = EXCLUDED.freight_amount_cent,
       discount_amount_cent = EXCLUDED.discount_amount_cent,
       freight_discount_cent = EXCLUDED.freight_discount_cent,
       payable_amount_cent = EXCLUDED.payable_amount_cent,
       selected_coupon_nos = EXCLUDED.selected_coupon_nos,
       context_payload = EXCLUDED.context_payload,
       contact_name = EXCLUDED.contact_name,
       contact_phone = EXCLUDED.contact_phone,
       remark = EXCLUDED.remark,
       created_at = EXCLUDED.created_at,
       updated_at = EXCLUDED.updated_at,
       paid_at = EXCLUDED.paid_at,
       canceled_at = EXCLUDED.canceled_at,
       deleted = FALSE,
       pay_no = EXCLUDED.pay_no,
       fulfillment_status = EXCLUDED.fulfillment_status,
       refund_status = EXCLUDED.refund_status,
       version = park_order.version + 1;

DELETE FROM park_order_item i
 USING tmp_legacy_consumption_order t
 WHERE i.order_no = t.order_no
   AND t.include_item = FALSE;

INSERT INTO park_order_item (
    order_no,
    line_no,
    item_id,
    item_type,
    item_name,
    category_id,
    brand_id,
    unit_price_cent,
    quantity,
    amount_cent,
    attributes,
    created_at
)
SELECT t.order_no,
       '1' AS line_no,
       CONCAT(t.order_no, '_ITEM_1') AS item_id,
       t.item_type,
       t.item_name,
       t.category_id,
       'LEGACY_IMPORT' AS brand_id,
       t.raw_amount_cent AS unit_price_cent,
       1 AS quantity,
       t.raw_amount_cent AS amount_cent,
       t.attributes,
       t.occurred_at
  FROM tmp_legacy_consumption_order t
 WHERE t.include_item = TRUE
ON CONFLICT (order_no, line_no) DO UPDATE
   SET item_id = EXCLUDED.item_id,
       item_type = EXCLUDED.item_type,
       item_name = EXCLUDED.item_name,
       category_id = EXCLUDED.category_id,
       brand_id = EXCLUDED.brand_id,
       unit_price_cent = EXCLUDED.unit_price_cent,
       quantity = EXCLUDED.quantity,
       amount_cent = EXCLUDED.amount_cent,
       attributes = EXCLUDED.attributes,
       created_at = EXCLUDED.created_at;

DELETE FROM park_order_status_event e
 USING tmp_legacy_consumption_order t
 WHERE e.order_no = t.order_no
   AND e.event_type = 'LEGACY_IMPORT';

INSERT INTO park_order_status_event (
    order_no,
    event_type,
    from_status,
    to_status,
    operator_type,
    operator_id,
    event_payload,
    created_at
)
SELECT t.order_no,
       'LEGACY_IMPORT' AS event_type,
       NULL AS from_status,
       t.order_status AS to_status,
       'SYSTEM' AS operator_type,
       'legacy-import' AS operator_id,
       jsonb_build_object(
           'eventName', '老系统历史订单导入',
           'remark', CONCAT('来源消费记录.xlsx / ', t.store_name),
           'legacyStatus', t.legacy_status,
           'legacyMemberNo', t.legacy_member_no
       ) AS event_payload,
       t.occurred_at
  FROM tmp_legacy_consumption_order t;

COMMIT;
""",
        encoding="utf-8",
    )


def write_summary(path: Path, summary: dict) -> None:
    lines = [
        "# 老系统消费订单导入汇总",
        "",
        f"- 生成时间: `{summary['generated_at']}`",
        f"- 输出目录: `{summary['output_dir']}`",
        f"- 原始订单行数: `{summary['orders']['total_rows']}`",
        f"- 正金额明细行: `{summary['orders']['positive_item_rows']}`",
        f"- 仅导订单头行: `{summary['orders']['header_only_rows']}`",
        f"- 全部正金额合计: `{cent_to_yuan_text(summary['orders']['positive_amount_cent'])}` 元 / `{summary['orders']['positive_amount_cent']}` 分",
        f"- 已完成正金额合计: `{cent_to_yuan_text(summary['orders']['valid_positive_amount_cent'])}` 元 / `{summary['orders']['valid_positive_amount_cent']}` 分",
        "",
        "## 状态分布",
    ]
    for key, value in sorted(summary["orders"]["status_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## 场景分布"])
    for key, value in sorted(summary["orders"]["scene_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## 问题计数"])
    for key, value in sorted(summary["issues_by_code"].items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend([
        "",
        "## 导入方式",
        "",
        "将本目录整体复制到目标数据库客户端可访问路径后，在该目录执行：",
        "",
        "```bash",
        "psql \"$DATABASE_URL\" -f load_import.sql",
        "```",
        "",
        "或在容器中切到本目录，再执行：",
        "",
        "```bash",
        "docker exec -w /tmp/legacy-order-import hellokitty-postgres psql -U hellokitty -d hellokitty_park -f load_import.sql",
        "```",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders-xlsx", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    output_dir = args.out
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = format_timestamptz(dt.datetime.now(LOCAL_TZ).replace(microsecond=0))
    issues: list[dict] = []
    orders, order_summary = load_orders(args.orders_xlsx, issues)

    counts = {
        "legacy_consumption_orders": write_csv(output_dir / "legacy_consumption_orders.csv", ORDER_COLUMNS, orders),
        "validation_issues": write_csv(output_dir / "validation_issues.csv", ISSUE_COLUMNS, issues),
    }
    write_load_sql(output_dir / "load_import.sql")
    summary = {
        "generated_at": generated_at,
        "output_dir": str(output_dir),
        "counts": counts,
        "orders": order_summary,
        "issues_by_code": {},
    }
    for issue in issues:
        code = issue["code"]
        summary["issues_by_code"][code] = summary["issues_by_code"].get(code, 0) + 1
    (output_dir / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(output_dir / "validation_summary.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
