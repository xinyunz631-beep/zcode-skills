#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/Users/zhangxinyun/Documents/HelloKitty乐园后端项目}"
DOC="$ROOT/docs/ops/production-middleware-access.local.md"
WG="$ROOT/docs/ops/production-wireguard-client.local.conf"

if [[ ! -f "$DOC" ]]; then
  echo "Missing production middleware doc: $DOC" >&2
  exit 1
fi

echo "# HelloKitty production middleware inventory (redacted)"
echo
echo "source: $DOC"
echo

awk '
  BEGIN {
    secret = "(密码|口令|pass|PASS|Password|password|token|TOKEN|secret|SECRET|PrivateKey|privatekey|Authorization|Cookie|签名|密钥)"
    keep = "(容器|地址|端口|数据库|用户名|用户|主机|API|Console|Management|VPN|AMQP|应用用户名|备份目录|类型|服务端|客户端)"
  }
  /^#/ {
    print
    next
  }
  /^\|/ {
    if ($0 ~ secret) {
      next
    }
    if ($0 ~ keep) {
      print
    }
    next
  }
' "$DOC"

if [[ -f "$WG" ]]; then
  echo
  echo "## WireGuard client summary (redacted)"
  echo "source: $WG"
  grep -E "^(Address|Endpoint|AllowedIPs|PersistentKeepalive) = " "$WG" || true
fi

echo
echo "Secrets are intentionally omitted. Read the local sensitive files only when a command needs a credential, and redact values in all user-facing output."
