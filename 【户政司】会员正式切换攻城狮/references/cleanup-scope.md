# Cleanup Scope

## Delete

### Orders and payments

- `park_order`, items, status events, fulfillment, inventory locks, refunds, and third-party compensation
- `pay_payment_record`, payment operation logs, and refund records
- admin order aftersale, logistics, remarks, reviews, risks, and export tasks
- third-party POS mobile order, return, and refund-compensation records

### Coupon operational data

- CRM and promotion member coupon instances
- coupon verification, claim, refund-return, budget, snapshot, exchange-code, and issue-flow records
- marketing and third-party coupon batches, code inventory, upload records, and export tasks

### Fast pass

- `admin_ticket_instance`
- `admin_ticket_instance_operation_log`

### Members

- CRM member profiles, stats, addresses, favorites, K-coin transactions, legacy binds, and phone dedup audits
- member annual-card assets
- member growth records, profile operation logs, member-code writeoff records, and import/export tasks
- new-user gift trigger records

## Preserve

- coupon and third-party coupon templates
- coupon packages
- promotion activities, rules, and holiday calendars
- member levels, benefits, growth schemes, and member schemes
- admin accounts, verifier accounts, roles, permissions, menus, and application configuration
- third-party POS sessions and endpoint configuration

## Scope Changes

Before adding a table, inspect its table comment, identity columns, foreign keys, and current production count. Add business facts only. Never add configuration tables merely because their names contain `member`, `coupon`, or `order`.
