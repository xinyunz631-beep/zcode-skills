#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="/tmp/cursor-screenshots"
mkdir -p "$OUT_DIR"
CDP="${CDP_PORT:-9222}"

usage() {
  cat <<EOF
Attach to Chrome with remote debugging on port $CDP.

Start Chrome once:
  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=$CDP

Usage:
  browser-cdp.sh screenshot <url>
  browser-cdp.sh text <url>
EOF
}

cmd="${1:-}"
url="${2:-}"
if [[ -z "$cmd" || -z "$url" ]]; then
  usage
  exit 1
fi

ts() { date +%Y%m%d-%H%M%S; }

NODE_PATH="${NODE_PATH:-$HOME/.npm-global/lib/node_modules}" CMD="$cmd" URL="$url" CDP="$CDP" OUT="$OUT_DIR/cdp-$(ts).png" node <<'NODE'
const { chromium } = require('playwright');
(async () => {
  const cdp = process.env.CDP || '9222';
  const url = process.env.URL;
  const cmd = process.env.CMD;
  const out = process.env.OUT;
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdp}`);
  const context = browser.contexts()[0] || await browser.newContext();
  const page = await context.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  if (cmd === 'screenshot') {
    await page.screenshot({ path: out, fullPage: true });
    console.log(out);
  } else {
    const title = await page.title();
    const text = await page.locator('body').innerText();
    console.log('TITLE:', title);
    console.log('---');
    console.log(text.replace(/\s+/g, ' ').trim().slice(0, 4000));
  }
  await page.close();
  await browser.close();
})().catch(e => {
  console.error('CDP failed:', e.message);
  console.error('Is Chrome running with --remote-debugging-port=' + (process.env.CDP || '9222') + '?');
  process.exit(1);
});
NODE
