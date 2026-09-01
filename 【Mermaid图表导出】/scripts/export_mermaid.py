#!/usr/bin/env python3
"""Render Mermaid .mmd files with mermaid-cli (mmdc)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_mmdc() -> str | None:
    found = shutil.which("mmdc")
    if found:
        return found

    candidates = [
        Path.home() / ".npm-global" / "bin" / "mmdc",
        Path.home() / ".nvm" / "versions" / "node",
        Path("/opt/homebrew/bin/mmdc"),
        Path("/usr/local/bin/mmdc"),
    ]

    for candidate in candidates:
        if candidate.name == "node" and candidate.exists():
            matches = sorted(candidate.glob("*/bin/mmdc"), reverse=True)
            if matches:
                return str(matches[0])
        elif candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a Mermaid .mmd file to PNG, SVG, or PDF.")
    parser.add_argument("input", help="Input Mermaid .mmd file")
    parser.add_argument("output", help="Output image path (.png, .svg, or .pdf)")
    parser.add_argument("--background", "-b", default="white", help="Background color, e.g. white or transparent")
    parser.add_argument("--theme", default=None, help="Mermaid theme, e.g. default, neutral, dark, forest")
    parser.add_argument("--width", "-w", type=int, default=None, help="Viewport width")
    parser.add_argument("--height", "-H", type=int, default=None, help="Viewport height")
    parser.add_argument("--scale", type=float, default=None, help="Puppeteer device scale factor")
    parser.add_argument("--config", default=None, help="Optional Mermaid config JSON file")
    parser.add_argument(
        "--puppeteer-config",
        default=None,
        help="Optional Puppeteer config JSON file. Defaults to a temporary no-sandbox config for local macOS use.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    mmdc = find_mmdc()
    if not mmdc:
        print("Mermaid CLI (mmdc) was not found. Install @mermaid-js/mermaid-cli first.", file=sys.stderr)
        return 127

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_config = None
    puppeteer_config = args.puppeteer_config
    if not puppeteer_config:
        temp_config = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        temp_config.write(
            '{"args":["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]}'
        )
        temp_config.close()
        puppeteer_config = temp_config.name

    cmd = [mmdc, "-i", str(input_path), "-o", str(output_path), "-b", args.background, "-p", puppeteer_config]
    if args.theme:
        cmd.extend(["-t", args.theme])
    if args.width:
        cmd.extend(["-w", str(args.width)])
    if args.height:
        cmd.extend(["-H", str(args.height)])
    if args.scale:
        cmd.extend(["-s", str(args.scale)])
    if args.config:
        cmd.extend(["-c", str(Path(args.config).expanduser().resolve())])

    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if temp_config:
        try:
            Path(temp_config.name).unlink(missing_ok=True)
        except OSError:
            pass
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        return result.returncode

    if not output_path.exists() or output_path.stat().st_size == 0:
        print(f"Render command completed but output is missing or empty: {output_path}", file=sys.stderr)
        return 1

    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
