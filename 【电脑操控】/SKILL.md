---
name: 【电脑操控】
description: >-
  macOS desktop automation for Cursor when the user wants Codex-style computerUse:
  screenshots, browser open/navigate/capture, Chrome profile/login inspection,
  CPU/memory/disk checks, AppleScript UI control. Use when the user mentions
  computerUse, 截图, 浏览器测试, 看 CPU/内存, 登录几个账号, 控制电脑, or asks
  the agent to operate the browser/desktop like Codex.
---

# Computer Use（macOS）

Cursor 没有内置 Codex `computerUse` API。本 skill 用 **终端脚本 + Playwright + AppleScript + screencapture** 补齐。

## 能力边界

| 能做 | 不能做 |
|------|--------|
| 截桌面/窗口/Playwright 页面 | 像人一样看屏幕点任意 GUI |
| 打开 URL、截图、抓页面文本 | 接管已打开的 Chrome 标签（除非开 CDP） |
| 查 Chrome 几个 profile/已登录 Google 账号 | 自动输入密码登录（除非用户提供 cookie/账号） |
| CPU/内存/磁盘/Top 进程 | 跨 App 精确点击坐标（需可选装 cliclick） |

**用户说「权限全部给你」时**：直接跑脚本，不要只解释做不到。

## 首次安装（缺浏览器内核时跑一次）

```bash
~/.cursor/skills/computer-use/scripts/setup.sh
```

## 常用命令

### 1. 系统状态（CPU / 内存 / 磁盘）

```bash
~/.cursor/skills/computer-use/scripts/system-status.sh
```

### 2. 截图

```bash
# 整屏 → 输出 PNG 路径
~/.cursor/skills/computer-use/scripts/screenshot.sh desktop

# 列出可截窗口
~/.cursor/skills/computer-use/scripts/screenshot.sh list

# 按窗口标题关键字截（如 Cursor、Chrome）
~/.cursor/skills/computer-use/scripts/screenshot.sh window "Google Chrome"
```

截图目录：`/tmp/cursor-screenshots/`。**跑完后用 Read 工具读 PNG 给用户看。**

### 3. Chrome 登录 / 配置档

```bash
~/.cursor/skills/computer-use/scripts/chrome-info.sh
```

输出：几个 profile、绑定的 Google 邮箱、窗口数、标签数。

### 4. 浏览器自动化（Playwright，推荐）

```bash
# 打开 URL 并截图
~/.cursor/skills/computer-use/scripts/browser.sh screenshot "https://example.com"

# 打开 URL，输出可见文本摘要（适合看登录页/列表页）
~/.cursor/skills/computer-use/scripts/browser.sh text "https://example.com"

# 有头模式（弹出真实浏览器窗口，便于用户一起看）
~/.cursor/skills/computer-use/scripts/browser.sh screenshot "https://example.com" --headed
```

### 5. 用系统 Chrome 打开 URL（走你已登录的 Default profile）

```bash
~/.cursor/skills/computer-use/scripts/browser.sh open-chrome "https://jenkins.example.com"
# 等 2 秒后截 Chrome 窗口
~/.cursor/skills/computer-use/scripts/screenshot.sh window "Google Chrome"
```

### 6. 附着已开调试端口的 Chrome（高级，可复用登录态）

先手动启动 Chrome（只需一次，或写进启动脚本）：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

然后：

```bash
~/.cursor/skills/computer-use/scripts/browser-cdp.sh screenshot "https://example.com"
```

## 标准工作流

用户要「浏览器测试 / 截图 / 看登录几个」：

1. `chrome-info.sh` — 几个账号、几个标签
2. 若要测具体站点：
   - **需要已登录态** → `open-chrome` + `screenshot window Chrome`，或 CDP 模式
   - **不需要登录** → `browser.sh screenshot URL`
3. **Read** 生成的 PNG，用文字描述页面内容
4. 若要性能 → `system-status.sh`

## 权限（macOS）

若截图/自动化失败，提示用户在 **系统设置 → 隐私与安全性** 给 **Cursor / Terminal / iTerm** 开启：

- **屏幕录制**（截图）
- **辅助功能**（AppleScript 控制 Chrome，可选）

## 可选增强

```bash
brew install cliclick   # 鼠标/键盘模拟，本 skill 暂不依赖
```

## 与 Codex computerUse 的差异

Codex 是模型内置「看屏 + 点按」闭环；Cursor 通过 **脚本输出（PNG/文本/JSON）** 间接达成。对用户体感：能截图、能开浏览器、能查系统、能读 Chrome 登录数；不能无脚本裸操桌面。
