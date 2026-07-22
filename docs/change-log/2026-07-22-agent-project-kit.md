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

## [ADD] 공유 지침 문서 라이프사이클 + 스킬 팬아웃 + schema 업그레이드 (kit 1.1.0)

요구사항 검증에서 확인된 미충족 5개 항목(신규 시 `AGENTS.md`/`CLAUDE.md` 생성, 유저 인터뷰,
기존 문서 병합 개편, 타 Agent 도구 수용, 유저 스킬 도구별 동기화)을 해소했다.

- **불변식 정밀화** (`AGENTS.md` §0-2): "installer는 tracked tree 절대 무수정"은 유지하되,
  공유 지침 문서의 생성·병합은 셋업 스킬이 사용자 인터뷰·명시적 승인 하에 수행하는 사용자
  작업으로 정의했다. 산출물은 사용자 소유 tracked 문서로 commit 허용.
- **템플릿 배포**: `payload/templates/AGENTS.template.md`(큰 그림 + 세부 규칙 TBD 구조)와
  `CLAUDE.template.md`(`@AGENTS.md` 포인터 전용)를 `.agent-project-kit/templates/`에
  local-only로 배포한다.
- **`agent-kit-init` 개편**: 사용자 인터뷰(문제/목표/스택/성공 기준/사용 Agent 도구) →
  템플릿 기반 초안 제시 → 승인 후 `AGENTS.md`+포인터 `CLAUDE.md` 생성 절차를 추가했다.
- **`agent-kit-adopt` 개편**: "자동 병합 금지"를 "무단 병합 금지"로 바꾸고, 기존 규칙을
  `AGENTS.md` 기준 canonical+포인터 구조로 병합하는 개편안을 diff로 제시 → 사용자 선택·승인
  후 반영하는 절차를 추가했다.
- **`agent-kit-skill-sync` 신설**: CONTEXT의 `선언된 Agent 도구` 목록(기본 Claude Code,
  Codex — 그 외 도구는 사용자에게 확인 후 추가) 전체에 사용자 스킬 생성·수정·삭제를 동일
  원본으로 동기화하고, 동작 검증 후 검증 산출물을 삭제하는 규칙.
- **CONTEXT.md 공통 규칙 보강**: 근거+검증 의무(구체 수치·출처), 문서 수정=사용자 기능 변경
  구분, 민감정보 구체 나열, 모델 효율 지침, 공유 지침 문서 절, Agent 도구 레지스트리.
- **manifest schema v1→v2**: `SCHEMA_VERSION=2`와 schema 이력 동결(`SCHEMA_SKILLS`,
  `SCHEMA_TEMPLATES`)을 도입했다. v1 manifest는 기록된 schema로 검증되고, 재설치 시 managed
  exclude block만 v2로 교체하는 업그레이드가 수행되며(원본 prefix bytes 보존), v1 설치본의
  직접 uninstall도 지원한다. `KIT_VERSION` 1.0.0 → 1.1.0.

검증 (실행 명령과 결과):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
# Ran 78 tests in 94.154s — OK (기존 70 + 신규 8)
```

신규 테스트: schema 이력 부분집합·미지원 version 거부·스킬 payload 구조(SchemaHistoryTests 4),
v1 설치본의 in-place 업그레이드/직접 제거(SchemaMigrationTests 2), `AGENTS.md`/`CLAUDE.md`/
사용자 스킬 commit이 guard를 통과하고 킷 경로는 0개, uninstall이 사용자 공유 문서를 보존
(SharedDocumentCommitTests 2).

미검증·한계:

- init 인터뷰, adopt 병합 개편, skill-sync의 실제 Claude Code/Codex 대화형 플로우는 자동
  테스트 범위 밖이다(스킬 본문의 구조 검증만 자동화). 실전 프로젝트 첫 적용 시 검증한다.
- Claude Code/Codex 외 도구(예시: MY_AI)의 지침 파일 규약은 도구별 공식 문서 확인을 스킬
  절차에 위임했고 킷이 자동 생성하지 않는다.
- 기존 v1 설치본 업그레이드 시 mutable `CONTEXT.md`는 사용자 상태로 보존되므로 신규 공통
  규칙(도구 레지스트리 등)은 자동 반영되지 않는다. doctor가 kit_version 불일치를 보고하며,
  새 규칙 반영은 재설치 후 CONTEXT 수동 병합이 필요하다.

파일: `payload/templates/`(신규 2), `payload/skills/agent-kit-skill-sync/`(신규),
`payload/skills/agent-kit-init|adopt/SKILL.md`, `payload/runtime/CONTEXT.md`,
`scripts/agent_project_kit.py`, `tests/test_harness.py`, `AGENTS.md`, `README.md`,
`GETTING-STARTED.md`, `docs/architecture.md`
