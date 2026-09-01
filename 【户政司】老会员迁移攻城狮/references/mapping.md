# HelloKitty 老会员迁移映射

## Source Workbooks

### 会员导出.xlsx

Expected header:

```text
编号, 姓名, 昵称, 性别, 生日, 手机号, 注册时间, 积分余额, 等级
```

### 消费记录.xlsx

Expected header:

```text
订单编号, 会员编号, 订单金额, 订单状态, 店铺名称, 订单日期
```

### 账户导出.xlsx

Expected header:

```text
会员编号, 账户类型, 状态, 开始时间, 结束时间, 实际余额, 可用余额
```

### k币账户.xlsx

Supported alternate header:

```text
账户编号, STATUS_ID, 账户类型, 会员编号, 姓名, 开始日期, 截止日期, 实际余额, 可用余额
```

The converter reads the member number from column 4. For this nine-column K-coin export, only `卡币账户` rows are imported. `活动币账户` rows remain in source audit totals but are excluded from profile balances, frozen balances, and import detail rows.

## Target Identity

| Target field | Rule |
| --- | --- |
| `member_no` | `LEGACY_<old_member_no>` |
| `platform` | `WECHAT` |
| `app_id` | `LEGACY_IMPORT` |
| `external_user_id` | `LEGACY:<old_member_no>` |
| `primary_card_no` | old member number |
| `crm_legacy_member_bind.legacy_member_no` | old member number |

## Profile Mapping

| Source | Target |
| --- | --- |
| `昵称` else `姓名` else `老会员` | `nick_name` |
| `手机号` | `phone`, only standard mainland mobile numbers are written to bind rows |
| `生日` Excel serial | `birthday` |
| `注册时间` Excel serial | `registered_at`, `created_at`, `updated_at` |
| `性别` M/男 | `MALE` |
| `性别` F/女 | `FEMALE` |
| empty/other gender | `UNKNOWN` |
| `等级` 初级会员/中级会员/高级会员 | `L1`/`L2`/`L3` |
| `积分余额` | `growth_value`, `points_balance` |
| original name and old member no | `remark` |

## Consumption Mapping

Valid paid statuses:

```text
已完成, 已确认, 已审核
```

Rows with those statuses contribute to:

- `order_count`
- `paid_amount_cent`
- `last_order_at`

Other statuses are preserved in validation summary only.

## Account Mapping

The following general mapping applies to the seven-column `账户导出.xlsx`:

| Source account type/status | Target |
| --- | --- |
| `储蓄账户` + `有效` | `principal_balance_cent` |
| `活动币账户` + `有效` | `gift_balance_cent` |
| `卡币账户` + `有效` | contributes to `card_balance_cent` |
| any account type + `冻结` | `frozen_balance_cent` |
| unknown account types | validation issue only |

`card_balance_cent` is calculated as `principal_balance_cent + gift_balance_cent + card_coin_balance_cent`.

For the nine-column `k币账户.xlsx`, override the general mapping: import only `卡币账户`; exclude every other account type, including `活动币账户`, from all target balances.

The validation report includes both source account totals by `账户类型|状态` and final profile asset totals so rehearsal and cutover imports can be reconciled without opening row-level CSVs first.

## SQL Loading

Run `load_import.sql` from the generated output directory using `psql`. It uses psql `\copy`, temp tables, and `ON CONFLICT` upserts.

Recommended rehearsal:

```bash
psql "$DATABASE_URL" -f load_import.sql
```

Use a database backup and a cutover window before production import.
