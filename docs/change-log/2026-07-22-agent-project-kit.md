# 2026-07-22 — agent-project-kit 전환

전제: 기존 `claude-project-kit`을 Claude Code/Codex 공용 프로젝트 로컬 하네스로 재설계했다.

## [REFACTOR] 공급자 중립 로컬 하네스

- canonical 이름을 `agent-project-kit`으로 바꾸고 저장소 지침은 `AGENTS.md`, Claude 진입점은
  이를 import하는 얇은 `CLAUDE.md`로 분리했다.
- Claude 전용 agent/settings/skill 템플릿을 제거하고, 한 payload에서 두 공급자의 공식 탐색
  경로로 같은 4개 스킬(`init`, `adopt`, `handoff`, `wrap-up`)을 배포한다.
- 공통 `CONTEXT.md`와 `HANDOFF.md`에 목표, Git 상태, 검증 성공·실패·미실행, 다음 행동을
  기록하여 Claude Code ↔ Codex 전환 시 세션 밖에서 복구하게 했다.
- 글로벌 `~/.claude`, `~/.codex`, `~/.agents`는 수정하지 않는다.

## [ADD] 무손상 설치·편입·진단·제거

- `bootstrap.sh`를 Git 2.31+·Python 3.10+ stdlib 코어의 얇은 launcher로 바꾸고 `install`, `--adopt`,
  `--doctor`, `--diff`, `--uninstall`을 제공한다.
- 대상의 tracked `AGENTS.md`, `CLAUDE.md`, `.gitignore`, dirty/staged/untracked 상태를 수정하지
  않는다. owned path 충돌, tracked path, symlink escape는 쓰기 전 실패한다.
- worktree adapter는 exact `$GIT_COMMON_DIR/info/exclude`로 숨기며 기존 bytes·mode를 원장에
  기록해 깨끗한 제거 때 그대로 복원한다.
- strict manifest allowlist와 containment 검사로 조작된 상대 경로·symlink parent를 삭제
  대상으로 신뢰하지 않는다. mutable context/handoff는 재설치에서 보존하고 수정 상태의 제거는
  전체 중단한다.
- local/worktree `core.hooksPath`를 scope별로 보존하며 기존 hook을 먼저 실행하고 킷 guard를
  마지막에 실행한다. 선택 config EOF managed block, Git 호환 config lock, 현재 branch/include의
  동적 이전 hook 탐색으로 순서와 사용자 설정을 보존한다. Git common-dir lock으로 lifecycle
  동시 실행을 직렬화한다.
- lifecycle 종료 직전 linked worktree/bare inventory, sibling collision, hook, status를 다시
  검사한다. bare+linked local-scope 설치와 실행 중 inventory 변경은 rollback한다.
- 파일 allowlist 밖의 기존 부모 디렉터리·mode/ACL은 삭제하지 않는다.

## [ADD] commit/push 격리와 보조 안전 장치

- 일반 `git add -A` 예방, force-add pre-commit 차단, 우회 생성된 outgoing commit의 pre-push
  차단, doctor drift 검사를 겹쳤다.
- 대표 secret 파일명·staged 내용과 recursive force delete, pipe-to-shell, force push 등 위험
  명령을 보조 guard가 검사한다. client hook은 `--no-verify`와 설정 변경으로 우회 가능하므로
  권한 경계라고 주장하지 않는다.
- payload allowlist와 provider skill byte parity를 테스트한다.

## [DOCS] 조사와 진실성 판정

- OpenAI/Anthropic/Claude Code/Codex/Git/Open Agent Skills 공식 자료를 구현 계약의 1차 근거로
  사용했다.
- Channel Talk, Select Star, WikiDocs, revfactory README와 개인 경험담은 아이디어 탐색·해설로
  분류했다. 독립 재현 없는 생산성 수치와 “공식화된 용어” 주장은 일반 사실로 채택하지 않았다.
- 설계 근거와 모든 URL은 `docs/research/harness-engineering.md`, 사용자 절차와 한계는
  `README.md`, `GETTING-STARTED.md`, `docs/architecture.md`에 기록했다.

## 검증

실행:

```bash
./tests/run.sh
```

실측 결과:

```text
Ran 70 tests in 122.961s
OK
```

같은 macOS 환경에서 launcher의 `python3`를 Python 3.10.20으로 고정해 다시 실행한 결과도
`Ran 70 tests in 125.657s`, `OK`였다.

같은 runner 안의 Bash 구문, Python AST, JSON parse, `git diff --check`도 exit 0이었다. 주요
회귀 축은 신규/unborn/adopt/linked-worktree, status·tracked blob 불변, 기존 hook chain,
local/worktree hook scope, force-add commit과 outgoing push, strict manifest, symlink, exclude
bytes·mode, config include 순서·Git lock·branch 동적 hook, lifecycle 중 worktree 변경,
interrupt rollback, common-dir lock, clean/modified uninstall, provider parity다.

GitHub Actions action pin은 GitHub API로 태그의 commit SHA와 대조했다.

- `actions/checkout@v7.0.1` → `3d3c42e5aac5ba805825da76410c181273ba90b1`
- `actions/setup-python@v7.0.0` → `5fda3b95a4ea91299a34e894583c3862153e4b97`

## 미검증·한계

- 실제 Claude Code/Codex UI의 프로젝트 trust·hook 승인과 조직 managed policy는 미실행이다.
- GitHub-hosted workflow는 이 변경을 push한 뒤에야 실행된다.
- Windows와 네트워크 파일시스템의 POSIX lock/권한 동작은 지원·검증하지 않았다.
- local-only 파일은 다른 clone/원격 환경으로 전파되지 않으며 checkout마다 재설치해야 한다.
- 권한 있는 사용자의 `git add -f` + 모든 `--no-verify` + hook 변경을 중앙 정책처럼 막지 않는다.
