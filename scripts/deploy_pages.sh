#!/usr/bin/env bash
# Rebuild site/data.json from the committed results and publish site/ to the gh-pages branch.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
python -m prpa.site
TMP=$(mktemp -d)
cp -r "$ROOT/site/." "$TMP/"
touch "$TMP/.nojekyll"
cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="Par Bahrae" -c user.email="225519193+ParBproject@users.noreply.github.com" commit -q -m "Deploy $(git -C "$ROOT" rev-parse --short HEAD)"
git push -q -f "$(git -C "$ROOT" remote get-url origin)" gh-pages
rm -rf "$TMP"
