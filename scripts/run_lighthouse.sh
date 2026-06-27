#!/usr/bin/env bash
# Run Lighthouse against a URL (mobile or desktop). Reports go to lighthouse-reports/.
set -euo pipefail

URL="${1:-https://trends-dashboard.fly.dev/}"
FORM="${2:-mobile}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/lighthouse-reports"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_BASE="$OUT_DIR/${FORM}-${STAMP}"

mkdir -p "$OUT_DIR"

case "$FORM" in
  mobile)
    LH_ARGS=(--form-factor=mobile)
    ;;
  desktop)
    LH_ARGS=(--preset=desktop)
    ;;
  *)
    echo "Usage: $0 [URL] [mobile|desktop]" >&2
    exit 1
    ;;
esac

echo "Lighthouse ${FORM} → ${URL}"
npx --yes lighthouse "$URL" \
  "${LH_ARGS[@]}" \
  --output=html,json \
  --output-path="$OUT_BASE" \
  --chrome-flags="--headless=new"

echo "HTML: ${OUT_BASE}.report.html"
echo "JSON: ${OUT_BASE}.report.json"
