#!/usr/bin/env bash
# claude-project-kit 부트스트랩 — 복사(기본) / 비교(--diff) / 기존 프로젝트 편입(--adopt).
#
# 사용법:   ./bootstrap.sh <대상 프로젝트 경로>           # 복사 (기존 파일은 절대 덮어쓰지 않음)
#           ./bootstrap.sh --diff <대상 프로젝트 경로>    # 비교만 (아무것도 수정하지 않음)
#           ./bootstrap.sh --adopt <대상 프로젝트 경로>   # 진행 중 프로젝트 편입
# 동작:     킷 자신의 위치를 기준으로 동작하므로 킷 체크아웃 경로와 무관. 재실행 안전.
# 복사 대상: CLAUDE.md(시드), .claude/ 전체, templates/gitignore → .gitignore,
#           templates/change-log-README.md → docs/change-log/README.md
# --diff:   동기화 대상(.claude/ — 킷 업데이트를 따라가는 파일)은 내용 비교 + unified diff,
#           프로젝트 소유 파일(CLAUDE.md 등 — 채워지며 달라지는 게 정상)은 존재만 확인.
#           차이/누락이 있으면 exit 1, 완전 동일하면 exit 0.
# --adopt:  클린 git 트리 요구(HEAD가 롤백 지점) → no-clobber 복사 + 기존 .gitignore에
#           누락된 보안 패턴만 append. 모든 변경은 미커밋으로 남겨 검토 후 커밋.
#           이후 대상 프로젝트에서 /kit-adopt 스킬로 CLAUDE.md 재편·settings 병합.
# --doctor: 하네스 무결성 점검(수정 없음) — §0 존재, settings JSON, 훅 구문/권한,
#           .gitignore 보안 패턴, 민감 파일 추적 여부, change-log 최신성.
#           오류(❌) 있으면 exit 1, 경고(⚠️)만 있으면 exit 0.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="copy"
case "${1:-}" in
  --diff)   MODE="diff";   shift ;;
  --adopt)  MODE="adopt";  shift ;;
  --doctor) MODE="doctor"; shift ;;
esac

if [ $# -ne 1 ]; then
  {
    echo "사용법: $0 [--diff|--adopt|--doctor] <대상 프로젝트 경로>"
    echo "  (기본)    킷을 대상에 복사 — 기존 파일은 덮어쓰지 않음"
    echo "  --diff    복사 없이 킷과 대상의 차이만 표시 (동기화 대상 .claude/ 중심)"
    echo "  --adopt   진행 중 프로젝트 편입 — 클린 트리 요구, 복사 + .gitignore 보안 패턴 append"
    echo "  --doctor  하네스 무결성 점검 — 아무것도 수정하지 않음, 오류 있으면 exit 1"
  } >&2
  exit 1
fi

if [ ! -d "$1" ]; then
  echo "오류: 대상 디렉토리가 없습니다: $1  (먼저 mkdir + git init)" >&2
  exit 1
fi
TARGET="$(cd "$1" && pwd)"

# 자기 자신 거부는 수정 모드에만 — 읽기 전용(--diff/--doctor)은 킷 자신도 점검 가능
if [ "$TARGET" = "$KIT_DIR" ] && { [ "$MODE" = "copy" ] || [ "$MODE" = "adopt" ]; }; then
  echo "오류: 킷 자신에게는 복사/편입할 수 없습니다." >&2
  exit 1
fi

if [ "$MODE" = "adopt" ]; then
  if [ ! -d "$TARGET/.git" ]; then
    echo "오류: --adopt 는 git 저장소에서만 동작합니다 (HEAD가 롤백 지점이 됨): $TARGET" >&2
    exit 1
  fi
  # 추적 파일의 미커밋 변경(스테이징 포함)이 있으면 중단 — 편입 변경과 섞이는 것 방지.
  # 언트래킹 파일(??)은 허용.
  if git -C "$TARGET" status --porcelain | grep -qv '^??'; then
    echo "오류: 커밋되지 않은 변경이 있습니다. 커밋(또는 stash) 후 다시 실행하세요." >&2
    git -C "$TARGET" status --short | grep -v '^??' | head -10 >&2
    exit 1
  fi
fi

# 동기화 대상(.claude/) 파일 목록 — 복사·비교가 같은 목록을 쓴다
kit_claude_files() {
  find "$KIT_DIR/.claude" -type f ! -name '.DS_Store' ! -name 'settings.local.json' \
    ! -name '*.pyc' ! -path '*/__pycache__/*' | sort
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

# ──────────────────────────────── --doctor 모드 ──────────────────────────────
if [ "$MODE" = "doctor" ]; then
  ERR=0; WARN=0
  ok()   { echo "  ✅ $1"; }
  warn() { echo "  ⚠️  $1"; WARN=$((WARN + 1)); }
  bad()  { echo "  ❌ $1"; ERR=$((ERR + 1)); }

  echo "── 하네스 점검: $TARGET"

  echo "[CLAUDE.md]"
  CM="$TARGET/CLAUDE.md"
  if [ ! -f "$CM" ]; then
    bad "CLAUDE.md 없음 — bootstrap.sh(신규) 또는 --adopt(기존) 실행 필요"
  else
    if grep -q "작업 원칙" "$CM"; then ok "§0 RULE(작업 원칙) 존재"; else
      bad "§0 RULE 없음 — /kit-adopt(기존 문서) 또는 /claude-md-init 필요"; fi
    if grep -q "0-4" "$CM"; then ok "§0-4(보안) 존재"; else warn "§0-4(보안) 없음"; fi
    if grep -qF "이 파일은 시드(seed)다" "$CM"; then
      warn "시드 마커 잔존 — /claude-md-init 미실행 상태"; else ok "시드 마커 제거됨"; fi
    TBD_N=$(grep -c "TBD" "$CM" || true)
    [ "$TBD_N" -gt 0 ] && echo "  ℹ️  TBD ${TBD_N}곳 (모르는 건 TBD가 규칙 — 정보용)"
  fi

  echo "[.claude/settings.json + 훅]"
  SJ="$TARGET/.claude/settings.json"
  if [ ! -f "$SJ" ]; then bad "settings.json 없음"; else
    if python3 -m json.tool "$SJ" > /dev/null 2>&1; then ok "settings.json JSON 유효"; else
      bad "settings.json JSON 깨짐"; fi
  fi
  if [ -d "$TARGET/.claude/hooks" ]; then
    while IFS= read -r h; do
      base=$(basename "$h")
      case "$h" in
        *.py) if python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "$h" 2>/dev/null; then
                ok "훅 구문 OK: $base"; else bad "훅 구문 오류: $base"; fi ;;
        *.sh) if bash -n "$h" 2>/dev/null; then ok "훅 구문 OK: $base"; else
                bad "훅 구문 오류: $base"; fi ;;
      esac
      [ -x "$h" ] || warn "실행 권한 없음: $base (chmod +x 권장)"
    done < <(find "$TARGET/.claude/hooks" -maxdepth 1 -type f \( -name '*.py' -o -name '*.sh' \) | sort)
  else
    warn ".claude/hooks/ 없음 — 안전 훅 미설치"
  fi

  echo "[.gitignore]"
  GI="$TARGET/.gitignore"
  if [ ! -f "$GI" ]; then bad ".gitignore 없음"; else
    if grep -qE '^\.env' "$GI"; then ok "비밀 파일(.env) 차단 패턴 존재"; else
      warn ".env 차단 패턴 없음 — --adopt가 append해줌"; fi
  fi

  if [ -d "$TARGET/.git" ]; then
    echo "[git 추적 상태]"
    TRACKED_SECRETS=$(git -C "$TARGET" ls-files | grep -E '(^|/)\.env$|\.pem$|(^|/)id_rsa|(^|/)secrets/' || true)
    if [ -n "$TRACKED_SECRETS" ]; then
      bad "민감 파일이 git에 추적되고 있음: $(echo "$TRACKED_SECRETS" | tr '\n' ' ')"
    else ok "추적 중인 민감 파일 없음"; fi

    echo "[change-log 최신성]"
    LAST_COMMIT=$(git -C "$TARGET" log -1 --format=%cs 2>/dev/null || true)
    NEWEST_LOG=$(find "$TARGET/docs/change-log" -maxdepth 1 -name '[0-9]*-*.md' 2>/dev/null \
                 | sed 's|.*/||; s|\.md$||' | sort | tail -1)
    if [ -z "$NEWEST_LOG" ]; then
      warn "change-log 일자 파일 없음 (docs/change-log/YYYY-MM-DD.md)"
    elif [ -n "$LAST_COMMIT" ] && [ "$NEWEST_LOG" \< "$LAST_COMMIT" ]; then
      warn "change-log(${NEWEST_LOG})가 마지막 커밋(${LAST_COMMIT})보다 오래됨 — /wrap-up 권장"
    else
      ok "change-log 최신 (${NEWEST_LOG})"
    fi
  else
    warn "git 저장소 아님 — 추적 상태·change-log 최신성 점검 생략"
  fi

  echo
  echo "── 결과: 오류 ${ERR} · 경고 ${WARN}"
  [ "$ERR" -eq 0 ] && exit 0 || exit 1
fi

# ─────────────────────────── 복사 모드 (기본 / --adopt 공용) ──────────────────
if [ "$MODE" = "copy" ] && [ ! -d "$TARGET/.git" ]; then
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

# 5) --adopt: 기존 .gitignore에 누락된 보안 패턴만 append (정확히 일치하는 줄이 없을 때만)
APPENDED=()
if [ "$MODE" = "adopt" ]; then
  GI="$TARGET/.gitignore"
  SEC_PATTERNS=('.env' '.env.*' '!.env.example' '*.pem' 'id_rsa*' 'secrets/' '.claude/settings.local.json')
  for p in "${SEC_PATTERNS[@]}"; do
    if ! grep -qxF "$p" "$GI" 2>/dev/null; then
      if [ ${#APPENDED[@]} -eq 0 ]; then
        printf '\n# ── claude-project-kit adopt: 보안 패턴 추가 ──\n' >> "$GI"
      fi
      printf '%s\n' "$p" >> "$GI"
      APPENDED+=("$p")
    fi
  done
fi

echo
echo "── 결과 ──────────────────────────────────"
if [ ${#CREATED[@]} -gt 0 ]; then
  printf '  생성: %s\n' "${CREATED[@]}"
fi
if [ ${#SKIPPED[@]} -gt 0 ]; then
  printf '  건너뜀(이미 존재): %s\n' "${SKIPPED[@]}"
fi
if [ "$MODE" = "adopt" ] && [ ${#APPENDED[@]} -gt 0 ]; then
  printf '  .gitignore 추가 패턴: %s\n' "${APPENDED[@]}"
fi
echo
if [ "$MODE" = "adopt" ]; then
  echo "다음 단계 (편입):"
  echo "  1. git status / git diff 로 변경 검토 — 모든 변경은 미커밋 상태"
  echo "     (롤백: git restore .gitignore + 위 '생성' 목록 파일 삭제)"
  echo "  2. cd \"$TARGET\" && claude   →  /kit-adopt 실행"
  echo "     (기존 CLAUDE.md에 §0 삽입·§1~9 재편, settings 병합, 보안 대조)"
  echo "  3. 검토 후 커밋"
else
  echo "다음 단계:"
  echo "  1. .gitignore 를 프로젝트에 맞게 수정 (데이터/모델/산출물 경로)"
  echo "  2. cd \"$TARGET\" && claude   →  /claude-md-init 실행 (CLAUDE.md TBD 채우기)"
  echo "  3. 첫 커밋: CLAUDE.md + .claude/ + .gitignore + docs/"
fi
