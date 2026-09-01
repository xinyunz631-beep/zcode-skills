#!/usr/bin/env bash
set -euo pipefail

NO_OPEN=false
for arg in "$@"; do
  case "$arg" in
    --no-open) NO_OPEN=true ;;
    -h|--help)
      echo "Usage: check-quota.sh [--no-open]"
      echo "  Opens Cursor Dashboard usage pages and prints local CLI snapshot."
      exit 0
      ;;
  esac
done

SPENDING_URL="https://cursor.com/dashboard/spending"
USAGE_URL="https://cursor.com/dashboard/usage"
SETTINGS_URL="https://cursor.com/settings"

echo "=== Cursor 额度检查 ==="
echo

# Local CLI snapshot (no billing quota)
if command -v agent >/dev/null 2>&1; then
  echo "【本地 CLI】"
  agent about 2>/dev/null || echo "  (agent about 不可用)"
  echo
  agent status 2>/dev/null || true
  echo
else
  echo "【本地 CLI】agent 未安装，跳过"
  echo
fi

echo "【月度剩余额度】CLI 无法读取，请查看 Dashboard："
echo "  限额指标 → Spending 页的 Included Usage 百分比（不是 Usage 美元数）"
echo "  - Auto+Composer 池剩余 %"
echo "  - API 池剩余 %"
echo "  - On-Demand 是否 Disabled"
echo
echo "  Spending:  $SPENDING_URL"
echo "  Usage:     $USAGE_URL"
echo "  Settings:  $SETTINGS_URL"
echo
echo "【会话 context】在 agent 交互会话里看 status line 的 ctx %（不是月度额度）"
echo

if [ "$NO_OPEN" = false ]; then
  if command -v open >/dev/null 2>&1; then
    open "$SPENDING_URL"
    sleep 0.3
    open "$USAGE_URL"
    echo "已在浏览器打开 Spending 与 Usage 页面。"
  else
    echo "未找到 open 命令，请手动打开上述链接。"
  fi
fi
