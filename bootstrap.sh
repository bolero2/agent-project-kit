#!/usr/bin/env bash
# claude-project-kit 부트스트랩 — 킷을 새 프로젝트에 복사하거나(기본), 차이를 비교한다(--diff).
#
# 사용법:   ./bootstrap.sh <대상 프로젝트 경로>           # 복사 (기존 파일은 절대 덮어쓰지 않음)
#           ./bootstrap.sh --diff <대상 프로젝트 경로>    # 비교만 (아무것도 수정하지 않음)
# 동작:     킷 자신의 위치를 기준으로 동작하므로 킷 체크아웃 경로와 무관. 재실행 안전.
# 복사 대상: CLAUDE.md(시드), .claude/ 전체, templates/gitignore → .gitignore,
#           templates/change-log-README.md → docs/change-log/README.md
# --diff:   동기화 대상(.claude/ — 킷 업데이트를 따라가는 파일)은 내용 비교 + unified diff,
#           프로젝트 소유 파일(CLAUDE.md 등 — 채워지며 달라지는 게 정상)은 존재만 확인.
#           차이/누락이 있으면 exit 1, 완전 동일하면 exit 0.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="copy"
if [ "${1:-}" = "--diff" ]; then
  MODE="diff"
  shift
fi

if [ $# -ne 1 ]; then
  {
    echo "사용법: $0 [--diff] <대상 프로젝트 경로>"
    echo "  (기본)  킷을 대상에 복사 — 기존 파일은 덮어쓰지 않음"
    echo "  --diff  복사 없이 킷과 대상의 차이만 표시 (동기화 대상 .claude/ 중심)"
  } >&2
  exit 1
fi

if [ ! -d "$1" ]; then
  echo "오류: 대상 디렉토리가 없습니다: $1  (먼저 mkdir + git init)" >&2
  exit 1
fi
TARGET="$(cd "$1" && pwd)"

if [ "$TARGET" = "$KIT_DIR" ]; then
  echo "오류: 킷 자신을 대상으로 지정할 수 없습니다." >&2
  exit 1
fi

# 동기화 대상(.claude/) 파일 목록 — 복사·비교가 같은 목록을 쓴다
kit_claude_files() {
  find "$KIT_DIR/.claude" -type f ! -name '.DS_Store' ! -name 'settings.local.json' | sort
}

# ──────────────────────────────── --diff 모드 ────────────────────────────────
if [ "$MODE" = "diff" ]; then
  RC=0
  DIFFERING=()
  echo "── 킷 ↔ 대상 비교: $TARGET"
  echo "[동기화 대상 — .claude/ (킷 업데이트를 따라가는 파일)]"
  while IFS= read -r src; do
    rel="${src#"$KIT_DIR"/}"
    dst="$TARGET/$rel"
    if [ ! -e "$dst" ]; then
      echo "  없음:  $rel   (bootstrap.sh <대상> 으로 추가 가능)"
      RC=1
    elif cmp -s "$src" "$dst"; then
      echo "  동일:  $rel"
    else
      echo "  다름:  $rel"
      DIFFERING+=("$rel")
      RC=1
    fi
  done < <(kit_claude_files)

  echo "[프로젝트 소유 — 복사 후 달라지는 게 정상이라 존재만 확인]"
  for rel in CLAUDE.md .gitignore docs/change-log/README.md; do
    if [ -e "$TARGET/$rel" ]; then
      echo "  있음:  $rel"
    else
      echo "  없음:  $rel"
      RC=1
    fi
  done

  if [ ${#DIFFERING[@]} -gt 0 ]; then
    echo
    echo "── 상세 diff (- = 대상의 현재 / + = 킷 버전) ──"
    for rel in "${DIFFERING[@]}"; do
      echo
      echo "◆ $rel"
      diff -u "$TARGET/$rel" "$KIT_DIR/$rel" || true
    done
    echo
    echo "반영 방법: 킷 버전을 받으려면 해당 파일을 킷에서 복사."
    echo "          반대로 대상의 개선이 범용적이면 킷으로 역수출(킷 수정 + change-log)."
  fi
  exit "$RC"
fi

# ──────────────────────────────── 복사 모드 (기본) ────────────────────────────
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
done < <(kit_claude_files)

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
