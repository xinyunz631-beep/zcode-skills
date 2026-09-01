#!/usr/bin/env bash
set -euo pipefail

echo "==> computer-use setup"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx not found. Install Node.js first." >&2
  exit 1
fi

echo "==> Installing Playwright Chromium (one-time, ~150MB)..."
npx playwright install chromium

mkdir -p /tmp/cursor-screenshots
echo "==> Done. Screenshots go to /tmp/cursor-screenshots/"
