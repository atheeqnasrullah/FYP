#!/usr/bin/env bash
# Render every Mermaid diagram in this folder to a vector PDF in ../figures/,
# which report.tex includes. Run from anywhere: bash docs/report/diagrams/build.sh
#
# Needs Node.js. Uses the mermaid-cli from npx unless MMDC points to a local mmdc.
# On Windows, set CHROME to your Chrome path if Puppeteer cannot find a browser, e.g.
#   CHROME="C:/Program Files/Google/Chrome/Application/chrome.exe" bash build.sh
set -euo pipefail
cd "$(dirname "$0")"

MMDC="${MMDC:-npx -y @mermaid-js/mermaid-cli@11.4.2}"
PUPPETEER_ARGS=()
if [ -n "${CHROME:-}" ]; then
    printf '{"executablePath":"%s","args":["--no-sandbox"]}\n' "$CHROME" > .puppeteer.json
    PUPPETEER_ARGS=(-p .puppeteer.json)
fi

for src in *.mmd; do
    out="../figures/${src%.mmd}.pdf"
    echo "rendering $src -> $out"
    $MMDC "${PUPPETEER_ARGS[@]}" -c mermaid-config.json -b white -w 3000 -i "$src" -o "$out" --pdfFit -q
done
rm -f .puppeteer.json
