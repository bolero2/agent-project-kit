#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

while IFS= read -r -d '' script; do
  bash -n "$script"
done < <(find . -path './.git' -prune -o -type f -name '*.sh' -print0)

PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import ast
import json
from pathlib import Path

root = Path.cwd()
skip_parts = {".git", ".ruff_cache", "__pycache__"}
for path in root.rglob("*"):
    if not path.is_file() or skip_parts.intersection(path.parts):
        continue
    relative = path.relative_to(root)
    if path.suffix == ".py":
        ast.parse(path.read_text(), filename=str(relative))
    elif path.suffix == ".json":
        json.loads(path.read_text())
PY

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

git diff --check
