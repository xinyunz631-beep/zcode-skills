# Reconciliation

Accept a cutover only when all checks pass.

## Source And Artifact Checks

- Every source workbook SHA-256 matches `cutover_manifest.json`.
- No validation issue has severity `ERROR`.
- Consumption and account missing-member references are both zero.
- Member and order converters agree on consumption row count and valid completed amount.
- Every generated artifact size and SHA-256 matches the manifest.
- For nine-column `k币账户.xlsx`, the built-in mapping gate passes: `imported_rows` and `legacy_account_detail` equal the source `卡币账户` count, all non-card rows are excluded, valid/frozen card amounts match profile balances cent-for-cent, and activity-coin balance is zero.

## Database Checks

- `crm_member_profile`, `crm_member_stat`, `crm_legacy_member_bind`, and `admin_member_growth_record` match generated row counts.
- Sum of points, member order count, paid amount, principal, gift/K-coin, card balance, and frozen balance matches `profile_asset_summary` exactly.
- `park_order` and `park_order_status_event` match source consumption rows.
- `park_order_item` matches positive-amount rows; zero and negative rows remain header-only.
- Coupon instances, coupon verification records, fast-pass instances and verification logs, payments, refunds, and non-import order facts remain zero.

## Migrated Member Binding Check

After database verification and write restoration, but before opening public traffic:

- Production `hellokitty-park-bff-service` must classify a migrated-member auto-bind as `registeredNow=false` and must not trigger or expose a new-user gift for a `LEGACY_` profile.
- Complete first phone authorization for one designated migrated member whose source channel is `legacyImport`.
- Run `verify-legacy-member-binding --member-no ... --out .../legacy-member-binding-verification.json`.
- Require a real mini-program `app_id/external_user_id`, one active phone profile, one original legacy bind, and complete historical-order phone scope.
- Require new-user-gift records, related CRM coupon instances, and related promotion coupon assets to all equal zero.

## Evidence

Retain:

- source workbooks or their immutable archive
- `cutover_manifest.json`
- validation summaries and issue CSVs
- full database custom dump and `backup_manifest.json`
- before/after inventory CSVs
- `database_verification.json`
- `legacy-member-binding-verification.json`
