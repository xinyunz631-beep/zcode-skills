---
name: 【Cursor额度查看】
description: >-
  Check Cursor subscription remaining usage and quota via the web Dashboard when
  the user asks about 剩余额度, 调用量, quota, usage limits, spending percent,
  monthly allowance, or a Codex-style /status for billing. Cursor has no public
  CLI usage API; this skill opens the right Dashboard pages and interprets the
  numbers.
---

# Cursor 剩余调用量 / 额度查看

Cursor **没有** Codex 式 `/status` 或公开 billing API。月度剩余额度只能看网页 Dashboard；CLI 仅能看套餐档位和当前会话 context。

## 触发后第一步

运行本地快照脚本，打开 Dashboard，并输出解读指引：

```bash
~/.cursor/skills/【Cursor额度查看】/scripts/check-quota.sh
```

若用户只要链接、不要开浏览器，加 `--no-open`。

## 本地能拿到什么

| 来源 | 内容 | 不是 |
|------|------|------|
| `agent about` | 套餐（Pro/Pro+/Ultra）、当前模型 | 剩余额度 |
| `agent status` | 登录邮箱 | 用量 |
| CLI `/usage` | streak、编辑统计 | 账单额度 |
| Status line `ctx %` | 当前会话 context 占用 | 月度池剩余 |

## Dashboard 看哪里（关键）

**限额以 Spending 百分比为准，不是 Usage 美元数。**

| 页面 | URL | 看什么 |
|------|-----|--------|
| 额度百分比 | https://cursor.com/dashboard/spending | **Included Usage**：Auto+Composer %、API %；到 100% 触发限速或按需计费 |
| 请求明细 | https://cursor.com/dashboard/usage | 每条请求的模型、token、估算费用 |
| 按需计费开关 | https://cursor.com/dashboard/spending | On-Demand → Monthly Limit：`Disabled` = 超额只限速不扣费 |

IDE 内：`Cursor Settings` → `Usage`。

## 两套额度池（个人计划）

1. **First-party 池**：Auto、Composer 2.5、Grok 4.5
2. **API 池**：手动指定的 Claude / GPT / Sonnet 等

两池独立计数，按**订阅日**每月重置，未用完不结转。

| 套餐 | API 包含（约） |
|------|----------------|
| Pro | $20/月 |
| Pro Plus | $70/月 |
| Ultra | $400/月 |

## 超额后行为

- **On-Demand Disabled**：100% 后限速/排队，不额外扣费
- **On-Demand 已开启**：按 API 单价继续计费，直到你设的上限

## 回复用户模板

```markdown
## Cursor 额度快照

**本地（CLI）**
- 套餐：{tier}
- 模型：{model}
- 会话 context：{ctx% 或「需在 agent 会话内看 status line」}

**月度剩余（需 Dashboard 确认）**
- Auto+Composer 池：{X% 已用 / Y% 剩余} 或「请到 Spending 页查看」
- API 池：{X% 已用 / Y% 剩余} 或「请到 Spending 页查看」
- On-Demand：{Disabled / 已开启 + 上限}

**解读**
- 看 **Spending 百分比**，忽略 Usage 页的美元估算
- 日常用 Auto 更省 API 池；Max Mode 和长 Agent 会话消耗更快

**链接**
- [Spending](https://cursor.com/dashboard/spending)
- [Usage 明细](https://cursor.com/dashboard/usage)
```

若用户贴了 Dashboard 截图或数字，按上表填入模板并给出是否接近限额、是否建议开新会话或换 Auto。

## 不要做

- 不要声称能从 CLI/API 直接读取月度剩余百分比（目前无公开接口）
- 不要把 `ctx %` 当成月度额度
- 不要把 Usage 页美元数当成计费上限
- Team/Enterprise 的 Admin API 不适用于个人 Pro 查额度

## 可选：Status line 补充 context

月度额度仍只能看 Dashboard；若用户还想在终端常驻看**会话** context，用 `statusline` skill 配置 `~/.cursor/statusline.sh`。
