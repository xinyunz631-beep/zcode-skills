#!/usr/bin/env bash
set -euo pipefail

LOCAL_STATE="$HOME/Library/Application Support/Google/Chrome/Local State"

echo "========== Chrome 配置档 / Google 登录 =========="
if [[ -f "$LOCAL_STATE" ]]; then
  python3 <<'PY'
import json, os
path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Local State")
with open(path) as f:
    data = json.load(f)
info = data.get("profile", {}).get("info_cache", {})
print(f"配置档数量: {len(info)}")
for k, v in info.items():
    name = v.get("name", "(无名)")
    email = v.get("user_name") or v.get("gaia_name") or "未登录 Google"
    print(f"  [{k}] {name} | {email}")
last = data.get("profile", {}).get("last_used", "未知")
print(f"最近使用: {last}")
PY
else
  echo "未安装 Chrome 或未找到 Local State"
fi

echo
echo "========== Chrome 运行状态 =========="
if osascript -e 'application "Google Chrome" is running' 2>/dev/null | grep -q true; then
  osascript <<'APPLESCRIPT'
tell application "Google Chrome"
  set wc to count of windows
  set tabCount to 0
  repeat with w in windows
    set tabCount to tabCount + (count of tabs of w)
  end repeat
  return "运行中 | 窗口: " & wc & " | 标签: " & tabCount
end tell
APPLESCRIPT
else
  echo "Chrome 未运行"
fi
