#!/usr/bin/env bash
# Prints the next vX.Y.Z tag. Existing tags are read from stdin, one per line.
# Usage: next_version.sh <major|minor|patch>
set -euo pipefail

latest=$(grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1 || true)
IFS=. read -r major minor patch <<< "${latest#v}"
major=${major:-0} minor=${minor:-0} patch=${patch:-0}

case "${1:-}" in
  major) echo "v$((major + 1)).0.0" ;;
  minor) echo "v$major.$((minor + 1)).0" ;;
  patch) echo "v$major.$minor.$((patch + 1))" ;;
  *) echo "Usage: next_version.sh <major|minor|patch>" >&2; exit 1 ;;
esac
