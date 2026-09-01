---
name: 【哈根达斯开发攻城狮】
description: Use when working as the Haagen-Dazs or 哈根达斯开发攻城狮 on HG mall, hg-mall, 周边商城, 哈根达斯订单, 支付, 满减, 商品, 物流, control backend, mini-program backend, or admin frontend changes across cbcadmin, console-hg-master, and eos-hg.
---

# 哈根达斯开发攻城狮

## Meeting Opening

When this skill is active, start the first user-facing update with:

`【哈根达斯开发攻城狮】`

Then show a short task list and keep progress visible.

## Code Directories

- Admin frontend: `/Users/zhangxinyun/Downloads/代码/cbcadmin`
- Console/control backend: `/Users/zhangxinyun/Downloads/代码/console-hg-master`
- HG EOS / mini-program backend: `/Users/zhangxinyun/Downloads/代码/eos-hg`

## Branch Rules

- `cbcadmin`: use and push `hgds-dev` for HG admin frontend changes.
- `console-hg-master`: use and push `console-master-hg` for HG control backend changes.
- `eos-hg`: use and push `eos-master-hg` for HG EOS / mini-program backend changes.
- Do not push HG changes to `console_lnj_master`; that branch belongs to 老娘舅.

## Working Scope

- `cbcadmin`: 周边商城控制台页面、商品管理、满减规则、订单列表、订单详情、支付/物流/退款展示。
- `console-hg-master`: 控制台后端接口、HG mall order detail/list APIs, 订单金额字段聚合、物流字段、运营配置。
- `eos-hg`: 哈根达斯小程序 / mwos / hg-mall 后端支付、订单、回调、订单明细同步逻辑。

## Workflow

1. Start from the exact evidence the user provides: screenshot, order number, request URL, response JSON, or failing UI state.
2. Identify which repo owns the behavior before editing. Frontend display-only issues usually belong to `cbcadmin`; API field or calculation source issues usually belong to `console-hg-master`; payment/order callback behavior usually belongs to `eos-hg`.
3. Keep fixes narrow. Do not rewrite shared mall table/detail components unless the request affects shared display behavior.
4. Preserve unrelated dirty files. Stage only files touched for the current HG task.
5. For commits, use `alibaba-commit-style`.

## Known HG Mall Notes

- 周边商城订单详情常见字段:
  - `price` may be cent-scaled from backend item rows.
  - `realPrice` may represent item-level post-product-discount amount.
  - `payMoney` / `payMoneyText` represent order-level actual payment.
  - `thirdDeliveryPay` / `deliveryPay` represent freight.
- 商品行金额展示 must stay internally closed:
  - `优惠金额 + 实付金额 = 单价 * 数量`
  - 1 分 item rows must not be rounded or allocated down to `0.00`.
- Top-level order cards and item rows may intentionally use different discount labels:
  - `商品优惠金额` can mean product/item discount such as `price - realPrice`.
  - `整单满减金额` can mean order-level full-reduction discount.

## Release Habit

- If the user says to commit or publish, commit only the requested repo changes and push the current branch.
- Mention commit hash and branch in the final response.
- If no build/test was run, state that plainly.
