---
name: 【户政司】会员正式切换攻城狮
description: Perform HelloKitty old-member rehearsal or formal production cutover from 会员导出.xlsx, 消费记录.xlsx, and 账户导出.xlsx or k币账户.xlsx. Use when Codex must preflight legacy member data, back up and clean all production orders, coupon instances and verification records, fast-pass ticket verification data, and member business data, then import members, K-coin balances, and historical consumption orders with count and amount reconciliation.
---

# 【户政司】会员正式切换攻城狮

Execute the cutover as separate, auditable phases. Never skip source validation, the full database backup, or the post-import reconciliation.

## Environment

- Work in `/Users/zhangxinyun/Documents/HelloKitty乐园后端项目` or a clean worktree from that repository.
- Start production access with `hkp-prod-middleware-tunnel start`.
- Connect PostgreSQL through `127.0.0.1:15432`, database `hellokitty_park`, user `hellokitty`.
- Read `PGPASSWORD` only from the local sensitive ops document. Never print it or put it in a script, manifest, commit, or answer.
- Use a `pg_dump/pg_restore` client whose major version is at least the production PostgreSQL major version. The script discovers Homebrew `libpq`; otherwise set `HKP_PG_DUMP` and `HKP_PG_RESTORE`.
- Use the bundled scripts in `scripts/`. Their version-controlled source is `ops/legacy-member-import` in the backend repository.

## Required Inputs

Accept exactly these business sources, regardless of their containing directory:

- `会员导出.xlsx`
- `消费记录.xlsx`
- `账户导出.xlsx` or the nine-column `k币账户.xlsx`

For the nine-column `k币账户.xlsx`, import only rows whose account type is `卡币账户`. Keep `活动币账户` in source audit totals, but exclude it from member balances, frozen balances, and import detail rows.

For formal cutover, regenerate all artifacts and backups from the final files. Never reuse rehearsal artifacts or a rehearsal database dump.

## Workflow

1. Before the maintenance window, require production `hellokitty-park-bff-service` to contain the legacy-member eligibility guard: a `LEGACY_` profile auto-bound by phone returns `registeredNow=false` and neither triggers nor exposes a new-user gift. A merged branch is not deployment evidence.
2. Confirm a maintenance window and run `freeze` to make new application database sessions read-only and rebuild existing connections.
3. Run `prepare_legacy_member_cutover.py` into a new timestamped directory.
4. Review `cutover_manifest.json`, both validation summaries, and both validation issue CSVs.
5. Stop when either issue CSV contains `ERROR`, any member reference is missing, or member/order converters disagree on counts or amounts.
6. Run `run_legacy_member_cutover.py inventory` and retain the CSV.
7. Run `backup` into a new empty directory. The command must pass the before/after write-freeze check, validate the custom dump TOC, and write a SHA-256 manifest.
8. Run `cleanup` only with the exact confirmation token printed by the script. The script must verify that the database has not changed since backup.
9. Confirm every table in the cleanup inventory is zero.
10. Run `import` only with the exact import confirmation token. It imports members and historical orders in one database transaction and performs pre-commit reconciliation.
11. Require `verify` to pass counts, points, CRM paid amount, imported order/item amounts, K-coin balances, and zero residual operational tables.
12. Run `unfreeze` only after verification passes, then confirm the role default is restored and application connections rebuild. Keep public traffic in maintenance mode.
13. Choose a designated migrated member that has at least one completed historical consumption order, bind it through the mini program, then run `verify-legacy-member-binding`. Do not open public traffic unless the check passes unique phone identity, the original legacy-member bind, phone-scoped historical-order visibility, and zero legacy-member new-user-gift records or coupon assets.
14. Retain the source checksums, artifacts, database dump, freeze state, inventory CSVs, `database_verification.json`, and `legacy-member-binding-verification.json` as the cutover evidence.

## Commands

Prepare artifacts:

```bash
python3 scripts/prepare_legacy_member_cutover.py \
  --members /path/会员导出.xlsx \
  --orders /path/消费记录.xlsx \
  --accounts /path/k币账户.xlsx \
  --out /path/HKP-cutover-artifacts \
  --batch-code HKP_LEGACY_CUTOVER_YYYYMMDD
```

Inventory and backup:

```bash
python3 scripts/run_legacy_member_cutover.py freeze \
  --state-file /path/HKP-write-freeze-state.json \
  --confirm HKP_FREEZE_PRODUCTION_WRITES

python3 scripts/run_legacy_member_cutover.py inventory --out /path/inventory-before.csv
python3 scripts/run_legacy_member_cutover.py backup \
  --out /path/HKP-db-backup-YYYYMMDDHHMMSS \
  --state-file /path/HKP-write-freeze-state.json
```

Cleanup and import:

```bash
python3 scripts/run_legacy_member_cutover.py cleanup \
  --backup-dir /path/HKP-db-backup-YYYYMMDDHHMMSS \
  --state-file /path/HKP-write-freeze-state.json \
  --confirm HKP_DELETE_ALL_ORDERS_COUPONS_MEMBERS

python3 scripts/run_legacy_member_cutover.py import \
  --artifacts /path/HKP-cutover-artifacts \
  --state-file /path/HKP-write-freeze-state.json \
  --confirm HKP_IMPORT_VALIDATED_LEGACY_DATA
```

Independent verification:

```bash
python3 scripts/run_legacy_member_cutover.py verify \
  --artifacts /path/HKP-cutover-artifacts \
  --state-file /path/HKP-write-freeze-state.json

python3 scripts/run_legacy_member_cutover.py unfreeze \
  --state-file /path/HKP-write-freeze-state.json \
  --artifacts /path/HKP-cutover-artifacts \
  --confirm HKP_RESTORE_PRODUCTION_WRITES

# Run immediately after the designated migrated member completes first phone authorization.
python3 scripts/run_legacy_member_cutover.py verify-legacy-member-binding \
  --member-no LEGACY_LPXXXXXXXX \
  --out /path/HKP-cutover-artifacts/legacy-member-binding-verification.json
```

## Safety Gates

- Do not combine backup, cleanup, and import into one opaque command.
- Do not use `TRUNCATE ... CASCADE`; the script names the allowed business tables explicitly and fails on an unexpected dependency.
- Preserve coupon templates, third-party coupon templates, coupon packages, promotion activities/rules, member levels/benefits/schemes, admin accounts, permissions, and application configuration.
- Treat duplicate or invalid phones as warnings: import the member profile, but do not create an unsafe phone bind.
- For `k币账户.xlsx`, `import` and `verify` must pass the built-in hard gate: imported/detail rows equal all and only `卡币账户` rows; excluded types equal every non-card account type; valid and frozen card amounts reconcile cent-for-cent; `活动币账户` contributes zero to `gift_balance_cent`.
- Do not start formal cleanup until the production BFF release excludes migrated members from new-user-gift eligibility. Branch merge or local tests do not prove the production BFF is updated.
- Do not open public traffic after database import until one migrated member with completed history passes `verify-legacy-member-binding`. More than one active profile for the phone, a bind that no longer points to the original legacy member number, any historical order outside the bound phone scope, or any legacy-member new-user-gift record or coupon asset is a failed cutover.
- Stop if the database changes during or after backup. Resume only after re-freezing writes and creating a new backup.
- Keep the freeze state file until `unfreeze` reports `status=restored`; if any phase fails after cleanup, leave writes frozen while repairing or rolling back.
- If cleanup succeeds but import fails, do not reopen traffic. Fix the artifact or SQL, rerun the idempotent import, and rerun verification.
- If rollback is required, keep traffic frozen and restore the validated custom dump under the production-access runbook. Do not improvise partial row restoration.

Read `references/cleanup-scope.md` before changing table scope. Read `references/reconciliation.md` before accepting a rehearsal or formal cutover.
