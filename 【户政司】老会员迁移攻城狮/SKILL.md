---
name: 【户政司】老会员迁移攻城狮
description: Use when working as 【户政司】老会员迁移攻城狮 to convert old-system member, consumption, and account Excel exports into new CRM database import data for cutover, dry-run validation, or migration rehearsals. Handles files named like 会员导出.xlsx, 消费记录.xlsx, and 账户导出.xlsx.
---

# 【户政司】老会员迁移攻城狮

## Branch And Release Rule

- For HelloKitty code/API/contract changes, commit on `uat`, push `origin uat`, then merge `uat` into `prod` and push `origin prod`.
- Do not trigger Jenkins or perform deployment by default. Report touched modules/artifacts for the user to publish through Jenkins unless the user explicitly asks this window to deploy.
- For read-only, coordination, testing, or diagnostic work, do not create commits unless the user asks for code or documentation changes.

## HelloKitty Environment Rules

- Runtime diagnostics and bug investigation target production/`prod` by default. The old UAT runtime has been released; do not query or verify against UAT unless the user explicitly says a new UAT environment exists.
- Production middleware access must use the local tunnel from the local ops docs. Before PostgreSQL/Redis/Nacos/RabbitMQ/XXL-Job access, run `hkp-prod-middleware-tunnel start`; for PostgreSQL use `127.0.0.1:15432`, database `hellokitty_park`, user `hellokitty`, and read the password only from the local sensitive docs.
- Code changes still use the branch flow: commit on `uat`, push `origin uat`, merge `uat` into `prod`, and push `origin prod`. Do not trigger Jenkins, deploy, or publish; the user manually clicks Jenkins.
- Test data, smoke identifiers, trace IDs, build numbers, temporary order numbers, user IDs, device numbers, and fixture names must use HelloKitty/HKP business prefixes and must not contain `CODEX`, `Codex`, or `codex`.

## Purpose

Convert old-system Excel exports into deterministic HelloKitty CRM import artifacts. The conversion is intended for rehearsals and cutover day: do not write directly to production until the generated validation summary has been reviewed.

## Workflow

1. Confirm the three input workbooks:
   - `会员导出.xlsx`: member profile source.
   - `消费记录.xlsx`: order count, paid amount, and last order source.
   - `账户导出.xlsx` or `k币账户.xlsx`: legacy account balance source.
2. Read `references/mapping.md` before changing mappings.
3. Run:

```bash
python3 ~/.codex/skills/hellokitty-legacy-member-migration/scripts/convert_legacy_member_exports.py \
  --members /path/会员导出.xlsx \
  --orders /path/消费记录.xlsx \
  --accounts /path/账户导出.xlsx \
  --out /path/output-dir
```

4. Review `validation_summary.md`, `validation_summary.json`, and `validation_issues.csv`.
5. Only after review, use `load_import.sql` with `psql` from the output directory to load the CSVs into the target database.

## Safety Rules

- The script uses deterministic new member numbers: `LEGACY_<old_member_no>`.
- It never requires openId from the old system. It imports old records as `platform=WECHAT`, `app_id=LEGACY_IMPORT`, `external_user_id=LEGACY:<old_member_no>`.
- It preserves the old member number in `primary_card_no` and `crm_legacy_member_bind`.
- It generates `COPY -> temp table -> INSERT ... ON CONFLICT` SQL for idempotent import.
- It does not import row-level old account details into production tables; it outputs account detail and summary CSVs for validation while loading aggregated balances into `crm_member_profile`.
- It does not store or print database credentials.

## Outputs

- `crm_member_profile.csv`
- `crm_member_stat.csv`
- `crm_legacy_member_bind.csv`
- `admin_member_growth_record.csv`
- `legacy_account_summary.csv`
- `legacy_account_detail.csv`
- `legacy_consumption_summary.csv`
- `validation_issues.csv`
- `validation_summary.json`
- `validation_summary.md`
- `load_import.sql`

## Default Mapping

Core mapping is documented in `references/mapping.md`. The important default assumptions are:

- `会员导出.积分余额` maps to both `crm_member_profile.growth_value` and `points_balance` for validation.
- `账户导出.储蓄账户` maps to `principal_balance_cent`.
- `账户导出.活动币账户` maps to `gift_balance_cent`.
- `账户导出.卡币账户` contributes to `card_balance_cent`.
- `账户导出.冻结` maps to `frozen_balance_cent` and is not added to available principal/gift/card.
- `k币账户.xlsx` uses the alternate nine-column layout `账户编号/STATUS_ID/账户类型/会员编号/姓名/开始日期/截止日期/实际余额/可用余额`; only `卡币账户` rows are imported. `活动币账户` rows remain visible in source totals but do not enter profile or frozen balances.
- Valid consumption statuses are `已完成`, `已确认`, and `已审核`.

If business confirms a different balance meaning, change the script constants and rerun; outputs are deterministic.
