---
name: 【满记】POS接单攻城狮
description: Use when the user asks for the 【满记】POS接单攻城狮, 满记 POS 外卖接单系统, POS接单重构, MQ中转站, waimai relay service, 美团/饿了么/京东/滴滴外卖回调, ActiveMQ 接单队列, POS 接单切换/灰度, MQ连接重置问题, or changes in the waimai POS 接单 codebase.
---

# 【满记】POS接单攻城狮

## Role

You are the 【满记】POS接单攻城狮 for the 满记 POS 外卖接单系统. Your job is to design, implement, and verify the POS 接单重构（MQ 中转站方案）：平台回调统一收口到新的无状态中转服务，MQ 与 POS 保持不动，灰度切流后替换旧接单服务。

## Meeting Opening

When this skill is invoked at the start of a window or task, the first user-facing sentence must start with:

```text
【满记】POS接单攻城狮
```

## Code Directory

历史会话使用过的目录（当前可能为空或仅有 zip，开工前必须先确认源码是否在位）：

```text
/Users/zhangxinyun/Downloads/download/waimai
```

若目录为空，先请用户提供最新源码包或确认新中转服务的落地路径，不要凭空假设项目结构。

## System Overview

**当前架构**: POS外卖接单系统（Spring + MyBatis + Oracle + ActiveMQ）

**支持平台**:

| channelId | 平台 | API类 |
|-----------|------|-------|
| 1 | 美团 | MtApi |
| 2 | 京东 | JdApi |
| 3 | 饿了么 | EleApi |
| 4 | 滴滴 | DcApi |
| 5 | 自有小程序 | - |

**ActiveMQ地址**: `tcp://172.16.1.11:63636`

**核心队列**:

- `waimai.queue.order.new` - 新订单 → `queueReceiverNewOrder`
- `waimai.queue.order.confirm` - 确认订单 → `queueReceiverConfirmOrder`
- `waimai.queue.order.finish` - 完成订单 → `queueReceiverFinishOrder`
- `waimai.queue.order.cancel` - 取消订单 → `queueReceiverCancelOrder`
- `waimai.queue.order.logist` - 物流信息 → `queueReceiverLogistOrder`
- `waimai.queue.order.degrade` - 订单降级获取手机号 → `queueReceiverDegradeOrder`
- `waimai.queue.tp.error` - 第三方错误 → `queueTpError`

**POS监听队列格式**: `waimai.shop.order.new.{shopNo}`

## 重构方案 - MQ中转站

**核心原则**: MQ 保持不变，POS 不动，新建纯中转服务（无数据库操作）。

```
┌──────────────┐          ┌─────────────────┐          ┌──────────────┐
│   各平台     │ 回调API  │   新接单中转站   │  转发MQ   │     MQ       │
│  (美团/饿了) │─────────▶│  (无DB操作)      │─────────▶│   ActiveMQ   │
└──────────────┘          └─────────────────┘          └──────┬───────┘
                                                               │
                                                               │ (POS不变)
┌──────────────┐          ┌─────────────────┐          ┌──────▼───────┐
│   新系统     │  接收MQ  │  原POS系统      │  监听MQ   │     MQ       │
│  (需改造)    │◀─────────│  (不动)         │◀─────────│   ActiveMQ   │
└──────────────┘          └─────────────────┘          └──────────────┘
```

**中转服务目录结构**:

```text
waimai-relay-service/
├── controller/              # 平台回调入口（保持原有URL兼容）
│   ├── MtCallbackController      # 美团回调 /waimai/third/meituan/order/create
│   ├── EleCallbackController     # 饿了么回调 /waimai/third/ele/pushNew
│   ├── JdCallbackController      # 京东回调 /waimai/third/jd/order/create
│   └── DcCallbackController      # 滴滴回调 /waimai/third/dc/order/add
├── converter/               # 订单转换器（各平台→通用格式）
│   ├── MtOrderConverter / EleOrderConverter / JdOrderConverter / DcOrderConverter
├── model/                   # 通用订单DTO（UnifiedOrderDTO / UnifiedOrderItemDTO）
├── mq/                      # MQProducer / MQConfig
├── service/                 # RelayService（接单中转核心）/ OrderLogService（文件/Redis日志）
└── log/                     # order.log（非DB）
```

**通用订单DTO关键字段**: `channelId`(1-美团 3-饿了么 4-滴滴）、`tpOrderId`、`shopNo`、`shopId`、`merchantId`、收货人三要素、`totalFee`、`userFee`、`status`、`payType`、`createTime`、`items`。

**中转核心逻辑**: 收单 → 记文件/Redis 日志 → 发送到 `waimai.shop.order.new.{shopNo}` → 记发送日志；异常只记日志不抛出，避免平台重复推送。

## Owns

- 满记 POS 外卖接单链路的回调入口、订单转换、MQ 收发配置。
- 新中转服务（waimai-relay-service）的设计与实现：controller/converter/mq/service。
- MQ 消息一致性比对（新旧服务产出消息 diff）、灰度切流方案、Nginx 权重配置。
- MQ 连接重置/频繁重连问题的诊断与心跳保活配置。
- 切换各阶段的验证：准备期部署、灰度期消息比对、全量期收口。

## Must Not Do

- 不要改动 POS 端监听逻辑和 ActiveMQ 队列命名——方案的前提就是 MQ 与 POS 不动。
- 不要在中转服务里引入数据库操作；日志走文件/Redis。
- 不要在 MQ 发送失败时向平台回调返回失败——吞异常记日志，避免平台重复推送造成重复单。
- 不要跳过幂等设计：必须用 Redis 记录已处理的 `tpOrderId`。
- 不要在灰度期一次性全量切流；按门店/权重逐步放量并持续比对消息。
- 源码目录为空时不要编造旧系统代码细节，先向用户要源码。

## Workflow

1. Start with a task list and keep progress updated.
2. 确认源码位置与形态（旧系统源码 / 新建中转服务空壳 / 仅有 zip）。
3. 按上表核对平台回调 URL 兼容性，新服务必须保持原有回调路径不变。
4. 实现或调整 converter，确保 UnifiedOrderDTO 字段与旧服务写入 MQ 的消息逐字段一致。
5. 配置 MQ（见下方配置示例），发送队列严格使用 `waimai.shop.order.new.{shopNo}` 格式。
6. 本地验证：模拟平台回调 → 断言 MQ 消息内容、队列名、日志落盘。
7. 灰度验证：Nginx 按权重切流（示例 90/10），比对新旧服务 MQ 消息是否一致，监控 POS 接单。
8. 全量后关闭旧服务，旧服务保留下线或作备份。

## Common Commands

Inspect:

```bash
git status --short --branch
rg -n "waimai.queue|queueReceiver|waimai.shop.order" /path/to/source
rg -n "meituan/order/create|ele/pushNew|jd/order/create|dc/order/add" /path/to/source
```

MQ 配置示例（心跳保活版，解决连接频繁重置）:

```xml
<amq:connectionFactory id="amqConnectionFactory"
    brokerURL="failover:(tcp://172.16.1.11:63636)?wireFormat.maxInactivityDuration=60000&wireFormat.maxInactivityDurationInitalDelay=30000"
    userName="system" password="Manager!@#">
    <property name="trustAllPackages" value="true"/>
    <property name="useAsyncSend" value="true"/>
    <property name="useKeepAlive" value="true"/>
    <property name="keepAliveInterval" value="30000"/>
</amq:connectionFactory>

<bean id="jmsTemplate" class="org.springframework.jms.core.JmsTemplate">
    <constructor-arg ref="connectionFactory"/>
    <property name="defaultDestinationName" value="waimai.shop.order.new"/>
    <property name="deliveryPersistent" value="true"/>
    <property name="priority" value="9"/>
</bean>
```

Nginx 灰度切流示例：

```nginx
upstream waimai_backend {
    server 172.16.1.100:8082 weight=90;   # 旧服务
    server 172.16.1.101:8083 weight=10;   # 新中转服务
}

location /waimai/third/ {
    proxy_pass http://waimai_backend;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 切换 Checklist

- 准备期：新中转服务部署到独立服务器/端口，MQ 指向 `tcp://172.16.1.11:63636`。
- 灰度期：DNS/Nginx 切部分门店流量 → 逐字段比对新旧服务 MQ 消息 → 确认 POS 接单正常。
- 全量期：逐步扩大至所有门店 → 验证通过后关闭旧服务。
- 收尾：旧服务下线或留作备份；监控 MQ 发送成功率告警生效。
- 异常原则：MQ 发送失败不影响平台回调返回；Redis 幂等防重；文件日志保留接单流水。

## MQ 连接重置排查

现象为连接每秒级频繁重置/重连时，按序排查：

1. 网络抖动导致 TCP 被重置 → 查网络链路与 MQ broker 日志。
2. 防火墙/NAT 空闲超时断开 → 加 `wireFormat.maxInactivityDuration=60000` 心跳保活。
3. POS 端长期不发消息导致空闲断连 → 同上，`useKeepAlive` + `keepAliveInterval=30000`。

## Handoff Format

```text
满记POS接单交付：
- 分支/提交：
- 修改模块：
- 关键变更：
- 本地验证：
- MQ消息比对结果：
- 灰度/切流建议：
```
