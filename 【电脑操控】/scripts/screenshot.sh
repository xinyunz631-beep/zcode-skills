#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="/tmp/cursor-screenshots"
mkdir -p "$OUT_DIR"

usage() {
  cat <<'EOF'
Usage:
  screenshot.sh desktop              # full screen
  screenshot.sh list                 # list window titles
  screenshot.sh window "<title>"     # window matching title (partial ok)
EOF
}

ts() { date +%Y%m%d-%H%M%S; }

cmd="${1:-desktop}"
shift || true

case "$cmd" in
  desktop)
    out="$OUT_DIR/desktop-$(ts).png"
    screencapture -x "$out"
    echo "$out"
    ;;
  list)
    osascript <<'APPLESCRIPT' 2>/dev/null || true
tell application "System Events"
  repeat with p in (every process whose background only is false)
    try
      repeat with w in (every window of p)
        set t to name of w
        if t is not "" then
          log (name of p as text) & " | " & t
        end if
      end repeat
    end try
  end repeat
end tell
APPLESCRIPT
    ;;
  window)
    title="${1:-}"
    if [[ -z "$title" ]]; then
      echo "ERROR: provide window title substring" >&2
      usage
      exit 1
    fi
    safe=$(echo "$title" | tr -cs 'A-Za-z0-9._-' '_')
    out="$OUT_DIR/window-${safe}-$(ts).png"
    # -l: window id via AppleScript
    wid=$(osascript <<APPLESCRIPT
tell application "System Events"
  repeat with p in (every process whose background only is false)
    try
      repeat with w in (every window of p)
        set t to name of w
        if t contains "$title" then
          return id of w as text
        end if
      end repeat
    end try
  end repeat
end tell
return ""
APPLESCRIPT
)
    if [[ -z "$wid" ]]; then
      echo "ERROR: no window matching '$title'. Run: screenshot.sh list" >&2
      exit 1
    fi
    screencapture -x -l"$wid" "$out"
    echo "$out"
    ;;
  *)
    usage
    exit 1
    ;;
esac
