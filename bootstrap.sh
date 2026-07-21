#!/usr/bin/env bash
# claude-project-kit 부트스트랩 — 킷을 새 프로젝트에 복사한다.
#
# 사용법:   ./bootstrap.sh <대상 프로젝트 경로>
# 동작:     킷 자신의 위치를 기준으로 복사하므로 킷 체크아웃 경로와 무관하게 동작.
#           이미 존재하는 파일은 절대 덮어쓰지 않는다(SKIP 표시). 재실행해도 안전.
# 복사 대상: CLAUDE.md(시드), .claude/ 전체, templates/gitignore → .gitignore,
#           templates/change-log-README.md → docs/change-log/README.md
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -ne 1 ]; then
  echo "사용법: $0 <대상 프로젝트 경로>" >&2
  exit 1
fi

if [ ! -d "$1" ]; then
  echo "오류: 대상 디렉토리가 없습니다: $1  (먼저 mkdir + git init)" >&2
  exit 1
fi
TARGET="$(cd "$1" && pwd)"

if [ "$TARGET" = "$KIT_DIR" ]; then
  echo "오류: 킷 자신에게는 복사할 수 없습니다." >&2
  exit 1
fi

if [ ! -d "$TARGET/.git" ]; then
  echo "⚠️  경고: $TARGET 은 git 저장소가 아닙니다. git init 후 실행을 권장합니다. (복사는 계속)"
fi

CREATED=()
SKIPPED=()

copy_one() { # $1=src(절대) $2=dst(절대)
  if [ -e "$2" ]; then
    SKIPPED+=("${2#"$TARGET"/}")
  else
    mkdir -p "$(dirname "$2")"
    cp "$1" "$2"
    CREATED+=("${2#"$TARGET"/}")
  fi
}

# 1) CLAUDE.md 시드
copy_one "$KIT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"

# 2) .claude/ 전체 (개인 로컬 설정·OS 잡파일 제외)
while IFS= read -r src; do
  rel="${src#"$KIT_DIR"/}"
  copy_one "$src" "$TARGET/$rel"
done < <(find "$KIT_DIR/.claude" -type f ! -name '.DS_Store' ! -name 'settings.local.json' | sort)

# 3) .gitignore 베이스
copy_one "$KIT_DIR/templates/gitignore" "$TARGET/.gitignore"

# 4) change-log 인덱스 스텁
copy_one "$KIT_DIR/templates/change-log-README.md" "$TARGET/docs/change-log/README.md"

echo
echo "── 결과 ──────────────────────────────────"
if [ ${#CREATED[@]} -gt 0 ]; then
  printf '  생성: %s\n' "${CREATED[@]}"
fi
if [ ${#SKIPPED[@]} -gt 0 ]; then
  printf '  건너뜀(이미 존재): %s\n' "${SKIPPED[@]}"
fi
echo
echo "다음 단계:"
echo "  1. .gitignore 를 프로젝트에 맞게 수정 (데이터/모델/산출물 경로)"
echo "  2. cd \"$TARGET\" && claude   →  /claude-md-init 실행 (CLAUDE.md TBD 채우기)"
echo "  3. 첫 커밋: CLAUDE.md + .claude/ + .gitignore + docs/"
