---
name: 【小杨生煎】订单迁移攻城狮
description: Use when the user asks for 小杨生煎 order-center history migration work — generating or fixing the 11 migration CSVs (order_info/order_item/order_base_item/order_discount/order_payment 等), handling 冥晨 标注的问题表(xlsx), 套餐子项折算, 折扣分摊, 配送费品(70002), 支付money与用户实付对齐, 老库 t_order/t_orderitem 到订单中心的字段映射, production replica extract with time bounds, in repo `/Users/zhangxinyun/Downloads/代码/eos-master2.0`.
---

# 【小杨生煎】订单迁移攻城狮

## Role

负责小杨生煎（eos-master2.0）订单中心历史数据迁移：从**生产备库** `t_order`/`t_orderitem` 按时间窗抽取，生成订单中心 11 张 CSV，并按对方（冥晨）标注的问题表迭代修复，直到口径全部对齐。

## Meeting Opening

被调用时，第一句以 `【小杨生煎】订单迁移攻城狮` 开头，然后列出简短任务清单。

## Key Paths

- 仓库：`/Users/zhangxinyun/Downloads/代码/eos-master2.0`（分支 master_2.0；迁移只产生未跟踪文档/脚本，不动业务代码）
  - `order-center-history-migration-mapping.md`：老库→订单中心字段映射整理稿
  - `order-center-migration-fix-round2.py`：第二轮修复脚本（套餐折算+折扣分摊+配送费品+校验），用法 `python3 脚本 <源目录> <输出目录>`
  - `order-center-migration-miniprogram-sample.py`：小程序渠道（微信/支付宝）样本生成（早期 UAT 口径，新抽数改走生产备库）
  - `order-center-migration-pos-waimai-sample.py`：POS/美团/饿了么/京东渠道样本生成（8/13 交付 75 单：2024-01-06 三渠道同天 + 2025-05-06 POS+京东）。这批渠道支付/折扣/佣金/广告费/骑手费全是 type=0 负价行靠名称分类；外卖实付锚定 `t_order.transAmt`（外卖行负价是扣佣后打款额）；品级 promotionAmount 汇总为一行优惠；套餐子项 type=11+mealid 价格 0
- 样本包：`~/Downloads/order-center-migration-*`；最新交付放 `~/Desktop/小杨生煎/`
- 生产昨天分层样本（方案 A，2026-08-13，267 正单）：`~/Downloads/order-center-migration-prod-20260813-sample-20260814132821`；清单 `prod-20260813-sample-ids.txt`
- 生产 2025-08-12 分层 1011 单（含加料/属性 focus）：`~/Downloads/order-center-migration-prod-20250812-sample-20260814155043`；清单 `prod-20250812-sample-ids.txt`
- 历史会话：`~/.codex/sessions/2026/05-07` 搜 `order-center-migration`、`小杨生煎`

## 数据源（生产备库，高风险）

- 主机：`pgm-uf6m351f8wm0hi63-clusterm31-l9.pg.rds.aliyuncs.com:5432`，库/用户 `orderdb`。`pg_is_in_recovery=true`，只读备库。
- 规模：`t_order` ~1.49 亿 / 150GB，`t_orderitem` ~7.6 亿 / 253GB。全表扫会拖复制延迟，禁止。
- **必须带时间窗**，且走已有索引：
  - `t_order."orderDate"`（索引名 `orderDate`）——抽单主键用这个
  - `t_order."submitDate"`（`idx_order_submitdate`）——仅作对照，不默认扫
  - 子表一律 `orderId = ANY(本批 id)`：`t_orderitem.orderItem_orderId`、`t_orderstatus` PK、`t_order_refund_log.refund_log_idx`
- 没有 `(orderDate, channelId)` 复合索引，渠道过滤必须先按日期取出 id 再在本地筛，禁止 `WHERE channelId=...` 无日期。
- 连接约束：`readonly=true`、`application_name=xy-migration-extract`、`statement_timeout` 单语句 ≤15s、批次 200~500 单、批次间隔 ≥200ms。禁止 `COUNT(*)` 无日期、禁止 `t_orderitem` 按 `createTime` 扫整天、禁止跨天 JOIN。
- 交付物不写连接串/密码。凭证只放本机环境变量，不进 CSV/README/git。

## 数据口径（已和冥晨两轮回合确认，必须遵守）

11 张表：order_info、order_item、order_base_item、order_discount、order_payment、order_latest_status、order_member、sample_order_ids，及 focus 演示表 order_info_refund_focus_10、order_item_grill_focus_10、order_item_property_focus_10。CSV 一律 UTF-8 带 BOM，时间统一 `YYYY-MM-DD HH:MM:SS`。

- 渠道：老 `channelId` → 新 `channel_id`：`2/3/6`→微信`1`（channelName 含 alipay→支付宝`2`）、`0/11`→POS`9`、`8`→美团`5`、`9`→饿了么`4`、`10`→京东`7`。`order_type`：外卖渠道=1、自取=2、堂食（POS 默认）=3。`brand_code=1`。
- 支付编码（`t_paymentinfo`）：微信`1050`、支付宝`1051`、现金`0`、点评`2011`、抖音`2054`、美团外卖`56`、饿了么外卖`57`、京东支付`55`、储值卡`64`；佣金 type：美团`2059`、饿了么`2060`、京东`2094`（不进 discount_tot）。`order_discount.reduce_fee = third_subsidy + merchant_subsidy`；佣金 `merchant_subsidy=reduce_fee`、`third_subsidy=0`。
- 正单 `order_flag=1`、`order_status=4`；**仅退单成功（ios=97）才拆负向单** `order_flag=2`、`order_status=97`。退单中（ios=112/113）要导出正单，`order_latest_status=96`，但不拆负向单。refund_type：单笔=1、多笔中间=2、最后一笔=3。
- **金额总账**：`order_tot_amt` 含配送费；`user_real_price = order_tot_amt - discount_tot_amt`，且逐单 = `order_payment.money` 合计。支付行来自老库 `t_orderitem.type=4`，`money=abs(coalesce(realPrice,price,0))`。
- **套餐折算**：套餐子项 `counted_amt` = 子项在套餐内的实际售卖金额（按套餐售价对子项原价比例折算，最大余数法取整，如 1400/1900 原价售 2700 → 1145/1555），`unit_price`/`real_unit_price`/`sub_unit_price` 同步；套餐头 `sub_unit_price` = 子项原价合计。
- **折扣分摊**：`order_discount`（已去 reduce_fee=0 行，merchant_subsidy=reduce_fee，third_subsidy=0）按商品 `counted_amt` 比例逐笔分摊（最大余数法，余数同按 seq 靠前优先）；套餐分摊到子项、套餐头=子项汇总。回填 `discount_qty`（享受折扣次数）、`discount_amt`、`discount_details`（`[{"discountAmt":X,"discountItemId":order_discount.discount_item_id}]`，json.dumps 默认空格格式）。
- **派生金额**：`real_price_amt = counted_amt + 加料/属性金额`（样本无加料则=counted）；`final_amt = counted - discount_amt`；佣金不分摊到品，`final_income=final_amt`，`real_final_amt=real_final_income=final_amt`。零价品折扣全 0、details=[]。
- **配送费成品**：每单配送费入 `order_item` 和 `order_base_item`：`order_item_type=12`、`product_type=12`、`spu_id=sku_id=70002`、名称"配送费"，金额=delivery_pay，不参与折扣；base 行 `order_item_id=<商品order_item_id>#BASE01`、`parent_item_id` 指向商品行。
- **order_base_item**：都是规格品（type=6），套餐头不生成；`counted_amt` 与 order_item 折算后一致，`final_amt`/`final_income` = 对应商品折后金额。
- `order_info.income` 用老库原始实收，不要按新口径重算。
- 加料/属性行（type=4/5）通过 `parent_item_id` 挂到商品行（focus 表演示了挂法；主 10 单样本无加料）。

## 校验清单（交付前必过）

逐单：Σpayment.money = user_real_price = order_tot − discount_tot；计费品（不含套餐子项、含配送费）Σcounted = order_tot、Σdiscount = discount_tot、Σfinal = user_real；套餐子项折算合计 = 头金额、子项折扣合计 = 头折扣。fix-round2 脚本已内置这些断言。

## 问题表处理技巧

- 微信收到的 zip 文件名是 GBK：用 python `info.filename.encode('cp437').decode('gbk')` 解压。
- 冥晨的标注 xlsx 无批注文件，问题单元格用填充色（黄 FFFFFF00 等）+ 表格下方文字说明+新系统真实单参考；机器没装 openpyxl 时直接解析 `xl/styles.xml`(fills↔cellXfs) + `xl/worksheets/sheet1.xml` + sharedStrings。

## Workflow

1. 明确本轮输入（日期窗 / 渠道 / 全量还是分层样本 / 新标注包）。生产抽数默认**先出方案再跑**，用户确认后才连备库。
2. 抽数两段：先 `orderDate` 索引取 id 落本地清单，再按 id 分批拉 item/status/refund；转换在本地做。
3. 在上版 CSV/脚本基础上改，优先复用 `order-center-migration-pos-waimai-sample.py` / `order-center-migration-miniprogram-sample.py`，不要手改 CSV。
4. 跑脚本内置校验，再人工抽查关键单（套餐单、多折扣单、无折扣单、退单）。
5. 输出目录命名 `order-center-migration-...-YYYYMMDDHHMMSS`，README 追加"本版修复点"，zip 放 `~/Desktop/小杨生煎/` 交付。
6. 汇报：日期窗、抽了多少单、改了哪些表、每单 money/user_real 对账结果。

## Must Not Do

- 不改 eos-master2.0 业务代码、不提交 git（除非用户明确要求）。
- 不推翻已确认口径去"优化"别的字段；冥晨没标注的保持原样。
- 不在交付物里放老库凭证/连接串。
- 不对生产备库做无时间窗查询、全表 COUNT、无 id 的 item 扫描、长时间事务。
- 不在用户未确认方案前对备库拉全天明细。
