#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="/tmp/cursor-screenshots"
mkdir -p "$OUT_DIR"

usage() {
  cat <<'EOF'
Usage:
  browser.sh screenshot <url> [--headed]
  browser.sh text <url> [--headed]
  browser.sh open-chrome <url>
EOF
}

cmd="${1:-}"
url="${2:-}"
shift 2 2>/dev/null || true
headed="false"
for arg in "$@"; do
  [[ "$arg" == "--headed" ]] && headed="true"
done

if [[ -z "$cmd" || -z "$url" ]]; then
  usage
  exit 1
fi

ts() { date +%Y%m%d-%H%M%S; }

case "$cmd" in
  open-chrome)
    open -a "Google Chrome" "$url"
    echo "Opened in system Chrome: $url"
    ;;
  screenshot)
    out="$OUT_DIR/browser-$(ts).png"
    NODE_PATH="${NODE_PATH:-$HOME/.npm-global/lib/node_modules}" HEADED="$headed" OUT="$out" URL="$url" node <<'NODE'
const { chromium } = require('playwright');
(async () => {
  const url = process.env.URL;
  const out = process.env.OUT;
  const headed = process.env.HEADED === 'true';
  const browser = await chromium.launch({ headless: !headed });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.screenshot({ path: out, fullPage: true });
  await browser.close();
  console.log(out);
})().catch(e => { console.error(e.message); process.exit(1); });
NODE
    echo "$out"
    ;;
  text)
    NODE_PATH="${NODE_PATH:-$HOME/.npm-global/lib/node_modules}" HEADED="$headed" URL="$url" node <<'NODE'
const { chromium } = require('playwright');
(async () => {
  const url = process.env.URL;
  const headed = process.env.HEADED === 'true';
  const browser = await chromium.launch({ headless: !headed });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  const title = await page.title();
  const text = await page.locator('body').innerText();
  const snippet = text.replace(/\s+/g, ' ').trim().slice(0, 4000);
  console.log('TITLE:', title);
  console.log('---');
  console.log(snippet);
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
NODE
    ;;
  *)
    usage
    exit 1
    ;;
esac
