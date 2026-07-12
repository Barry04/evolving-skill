#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$SCRIPT_DIR}"
SOURCE_SKILL_DIR="$REPO_ROOT/skill"

if [ ! -d "$SOURCE_SKILL_DIR" ]; then
  echo "Error: Skill directory not found: $SOURCE_SKILL_DIR (run this script from the bundle or repo root)" >&2
  exit 1
fi

shopt -s nullglob
SKILL_DIRS=("$SOURCE_SKILL_DIR"/*/)
if [ ${#SKILL_DIRS[@]} -eq 0 ]; then
  echo "Error: No skills found under $SOURCE_SKILL_DIR" >&2
  exit 1
fi

for SKILL_DIR in "${SKILL_DIRS[@]}"; do
  if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
    echo "Error: Missing SKILL.md: $SKILL_DIR" >&2
    exit 1
  fi
done

TOOL_DIRS=(
  "${CODEX_HOME:-$HOME/.codex}/skills"
  "$HOME/.claude/skills"
  "$HOME/.cursor/skills"
)

for TOOL_DIR in "${TOOL_DIRS[@]}"; do
  mkdir -p "$TOOL_DIR"
done

TOTAL=0
for SKILL_DIR in "${SKILL_DIRS[@]}"; do
  [ -d "$SKILL_DIR" ] || continue
  SKILL_NAME=$(basename "$SKILL_DIR")
  for TOOL_DIR in "${TOOL_DIRS[@]}"; do
    TARGET="$TOOL_DIR/$SKILL_NAME"
    rm -rf "$TARGET"
    cp -R "$SKILL_DIR" "$TARGET"
  done
  echo "  installed: $SKILL_NAME"
  TOTAL=$((TOTAL + 1))
done

echo ""
echo "Done. Installed $TOTAL skill(s) to: ${TOOL_DIRS[*]}"
echo "Source: $SOURCE_SKILL_DIR"
