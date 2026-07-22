#!/usr/bin/env bash
# Stop 훅 — 턴 종료 시 스테이징된 파일에서 비밀(민감 파일명·시크릿 패턴)을 검사한다.
# .gitignore(예방) → 권한 deny(읽기 차단)에 이은 3번째 방어선: 커밋 직전 검출.
# exit 2 = Claude에게 정리 지시(stderr 전달). 같은 정지 시도에서 재검사는 1회만.

INPUT=$(cat 2>/dev/null || true)
# stop 훅 재진입(무한 루프) 방지 — 이 훅 때문에 이미 계속된 턴이면 통과
if printf '%s' "$INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    exit 0
fi

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
STAGED=$(git diff --cached --name-only --diff-filter=d 2>/dev/null)
[ -z "$STAGED" ] && exit 0

VIOLATIONS=""

# 1) 민감 파일명 검사 (허용: .env.example / .env.sample / .env.template)
while IFS= read -r file; do
    base=$(basename "$file")
    case "$base" in
        .env.example|.env.sample|.env.template) continue ;;
    esac
    case "$base" in
        .env|.env.*|*.pem|*.p12|id_rsa*|id_ed25519*|id_ecdsa*|credentials.json|service-account*.json|secrets.json|.npmrc)
            VIOLATIONS="${VIOLATIONS}
  - 민감 파일 스테이징됨: $file" ;;
    esac
done <<< "$STAGED"

# 2) 스테이징된 내용(인덱스 기준, 워킹트리 아님)에서 시크릿 패턴 검사
PATTERNS=(
    'AKIA[0-9A-Z]{16}'
    'ghp_[A-Za-z0-9]{36}'
    'github_pat_[A-Za-z0-9_]{22,}'
    'xox[baprs]-[A-Za-z0-9-]{10,}'
    '[-]{5}BEGIN[ A-Z]*PRIVATE KEY'
    '(api[_-]?key|secret[_-]?key|password|token)[[:space:]]*[:=][[:space:]]*["'\''][A-Za-z0-9+/=_-]{16,}'
)
while IFS= read -r file; do
    CONTENT=$(git show ":$file" 2>/dev/null) || continue
    for p in "${PATTERNS[@]}"; do
        if printf '%s' "$CONTENT" | grep -qE "$p"; then
            VIOLATIONS="${VIOLATIONS}
  - 시크릿 의심 패턴: $file"
            break
        fi
    done
done <<< "$STAGED"

if [ -n "$VIOLATIONS" ]; then
    printf '커밋 중단 필요(시크릿 검사 훅):%s\n스테이징에서 제외(git restore --staged <파일>)하고, 실제 비밀이면 즉시 폐기·회전할 것. 오탐이면 사용자에게 보고할 것.\n' "$VIOLATIONS" >&2
    exit 2
fi
exit 0
