#!/usr/bin/env bash
# agent-project-kit launcher. All installation logic lives in a stdlib-only
# Python program so paths containing spaces and linked worktrees are handled
# consistently.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$KIT_DIR/scripts/agent_project_kit.py" "$@"
