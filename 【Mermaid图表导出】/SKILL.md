---
name: 【Mermaid图表导出】
description: Export Mermaid diagrams, sequence diagrams, flowcharts, architecture diagrams, and API timing diagrams to image files. Use when Codex needs to create PNG/SVG/PDF images from Mermaid text, write .mmd source files, render diagrams with mermaid-cli/mmdc, or deliver local diagram images for user review.
---

# Mermaid Export

## Workflow

1. Write Mermaid source to a `.mmd` file in a project-appropriate output directory, usually `docs/` for repository documentation or a user-specified path.
2. Prefer the bundled script:
   ```bash
   python3 <skill_dir>/scripts/export_mermaid.py input.mmd output.png --background white
   ```
3. Render PNG by default unless the user asks for SVG or PDF. Use `.svg` or `.pdf` as the output extension for those formats.
4. Use descriptive filenames, for example `hg-mall-main-flow.mmd` and `hg-mall-main-flow.png`.
5. After rendering, verify the output exists and has a nonzero size. For image deliverables in the Codex desktop app, show the image with an absolute Markdown image path.
6. Keep the `.mmd` source next to the exported image unless the user explicitly asks for images only.

## Script

`scripts/export_mermaid.py` wraps `mmdc` and handles common local PATH issues. It searches `PATH` first, then common user install locations such as `~/.npm-global/bin/mmdc`.
By default it passes a temporary Puppeteer no-sandbox config, which avoids common local macOS Chromium launch failures.

Useful options:

```bash
python3 <skill_dir>/scripts/export_mermaid.py diagram.mmd diagram.png
python3 <skill_dir>/scripts/export_mermaid.py diagram.mmd diagram.svg --background transparent
python3 <skill_dir>/scripts/export_mermaid.py diagram.mmd diagram.png --width 2200 --height 1600
python3 <skill_dir>/scripts/export_mermaid.py diagram.mmd diagram.png --theme neutral --scale 2
```

If `mmdc` is missing, tell the user Mermaid CLI is not installed instead of rewriting a renderer from scratch.

## Diagram Guidelines

- Use quoted participant or node labels when labels contain spaces, punctuation, parentheses, or Chinese text.
- For sequence diagrams, keep participant names short and put details in message labels.
- For large diagrams, increase width/height rather than shrinking text.
- Use `--background white` for screenshots or documents unless transparency is requested.
- If rendering fails, first validate Mermaid syntax and remove unsupported punctuation from IDs while keeping display labels quoted.
