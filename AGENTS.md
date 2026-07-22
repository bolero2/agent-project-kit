# AGENTS.md — agent-project-kit

> 이 저장소의 Claude Code와 Codex가 함께 읽는 canonical 작업 지침이다.
> Claude Code는 `CLAUDE.md`의 import를 통해 이 파일을 읽는다.

## 0. 작업 원칙

### 0-1. 근거의 정직성

- 관측 사실·출처가 있는 사실·추론·미확인을 구분한다.
- 수치에는 실행 명령, 로그 또는 문서 출처를 붙인다. 실행하지 않은 검사는 `미실행`으로
  표시하고 성공과 실패를 모두 보고한다.
- 가설은 허용하지만 검증된 사실처럼 말하지 않는다. 가능한 경우 가장 작은 검사로 확인한다.

### 0-2. 대상 프로젝트 격리 — 제품 불변식

- 킷을 설치한 대상 프로젝트의 commit/push tree에는 킷 소유 파일이 들어가면 안 된다.
- installer는 대상의 tracked tree를 절대 수정하지 않는다. 대상의 tracked `AGENTS.md`,
  `CLAUDE.md`, `.gitignore`, 프로젝트 설정과 사용자 변경을 덮어쓰거나 자동 수정하지 않는다.
- 공유 지침 문서(`AGENTS.md` canonical + `CLAUDE.md` 포인터)의 생성·병합은 installer가
  아니라 셋업 스킬(`agent-kit-init`/`agent-kit-adopt`)이 사용자 인터뷰와 명시적 승인 하에
  수행한다. 그 산출물은 사용자 소유 tracked 문서이며 commit/push가 허용된다.
- 격리는 정확한 local exclude, manifest, pre-commit/pre-push guard, doctor로 방어한다.
  `git add -f`와 `--no-verify`를 고의로 함께 쓰는 관리자까지 막는다고 과장하지 않는다.
- 글로벌 `~/.claude`, `~/.codex`, `~/.agents`는 읽기·수정하지 않는다. 모든 설치는 대상
  Git 프로젝트 범위에 한정한다.

### 0-3. 도구 중립성과 단일 소스

- 공통 규칙·handoff·스킬 본문·검사 로직은 한 벌만 유지한다.
- Claude Code와 Codex 어댑터는 공식 탐색 경로의 차이만 가진다. 한쪽 기능을 바꾸면 parity
  테스트로 다른 쪽도 확인한다.
- 세션을 바꾸기 전 공통 `HANDOFF.md`에 목표, 상태, 검증, 실패, 다음 행동을 남긴다.
- 도구나 모델 이름에 정책을 결박하지 않는다. 복잡성은 측정된 실패가 있을 때만 추가한다.

### 0-4. 안전한 변경

- 이 저장소는 사용자 변경이 섞인 dirty worktree일 수 있다. 관련 없는 변경을 되돌리지 않는다.
- 파일 배포는 명시적 allowlist를 사용한다. 디렉터리 전체를 동적으로 패키징하지 않는다.
- 대상 경로의 symlink, tracked-path 충돌, 기존 tool config/hook 충돌은 쓰기 전에 검사한다.
- uninstall은 전체 preflight가 깨끗할 때만 제거한다. 수정본이나 mutable state가 있으면 어떤
  파일·설정도 제거하지 않고 중단한다.
- 토큰·키를 대화, 명령 인자, URL, git config 값, 추적 파일에 넣지 않는다.

### 0-5. living document

- 주요 결정, 실측 반증, 지뢰, 스코프 변경, 마일스톤 완료 시 이 문서를 즉시 현행화한다.
- 현재 사실만 간결히 유지하고 오래된 이력은 `docs/change-log/` 또는 ADR로 옮긴다.
- 실행·운영 문서에는 해당 범위의 전제, 복사 가능한 명령, 해석, 검증 앵커를 남긴다.

## 1. 프로젝트 개요

`agent-project-kit`은 신규 또는 진행 중인 Git 프로젝트에 프로젝트 로컬 agentic-development
하네스를 설치하는 CLI다. Claude Code와 Codex가 같은 규칙·스킬·handoff를 사용하며 세션 한도,
작업 특성 또는 사용자 선택에 따라 서로 이어서 작업할 수 있게 한다.

성공 기준:

- 설치 전후 대상의 사용자 Git 상태와 tracked blob이 변하지 않는다.
- 일반 `git add -A && git commit && git push`에 킷 소유 경로가 포함되지 않는다.
- Claude Code와 Codex가 동일한 local state와 의미적으로 동일한 스킬을 발견한다.
- 재설치, doctor, 제거가 멱등이며 기존 프로젝트 설정·훅과 공존하거나 안전하게 중단한다.

## 2. 저장소 구조

```text
bootstrap.sh                 # 안정적인 CLI 진입점
scripts/                     # Python stdlib 설치·진단·제거 코어
payload/                     # 명시적으로 배포하는 공통 runtime/skills/hooks
tests/                       # 격리·보안·도구 parity 회귀 테스트
docs/research/               # 출처 등급과 설계 근거
docs/change-log/             # 이 킷 저장소의 변경 이력
AGENTS.md · CLAUDE.md        # 이 킷 저장소의 canonical 지침과 Claude import
```

## 3. 핵심 결정과 근거

- **대상 Git 저장소 필수**: Git 밖에서는 commit 격리를 검증할 수 없으므로 설치하지 않는다.
- **프로젝트 `.gitignore` 무수정**: 저장소 로컬·비공유 패턴은 Git의
  `$GIT_COMMON_DIR/info/exclude`에 정확한 root-anchored 경로로 기록한다.
- **공통 코어 + 얇은 어댑터**: 긴 지침의 복제를 피하고 Claude/Codex 전환 드리프트를 막는다.
- **내구성 있는 handoff**: 세션 컨텍스트에 의존하지 않고 다음 도구가 사실·실패·다음 행동을
  복원하게 한다.
- **다층 Git 방어**: ignore는 force-add를 막지 못하고 client hook은 우회 가능하므로 예방,
  commit 검사, push 검사, doctor를 겹친다.
- **원장을 불신하는 제거**: manifest의 schema·allowlist·hash·경로 containment를 먼저 검증하고
  common-dir lock 아래에서만 lifecycle 변경을 수행한다.
- **로컬 설정 무손실**: `info/exclude` raw bytes·mode와 local/worktree hook scope를 원복하며,
  설치 후 사용자 변경이 있으면 전체 제거를 중단한다.
- **Git config 순서 보존**: 선택 config의 EOF managed block과 Git 호환 lock을 사용하며,
  dispatcher는 현재 branch/include 문맥의 직전 hook을 동적으로 chain한다.
- **공유 지침 문서는 스킬이 생성**: installer는 비대화형이므로 인터뷰가 필요한
  `AGENTS.md`(canonical) + `CLAUDE.md`(포인터) 생성·병합은 첫 에이전트 세션의 셋업 스킬이
  사용자 승인 하에 수행한다. installer의 "tracked tree 무수정" 불변식은 그대로 유지된다.
- **manifest schema 이력 동결**: 배포 payload가 바뀌면 `SCHEMA_VERSION`을 올리고 과거
  schema의 allowlist를 코드에 동결한다(`SCHEMA_SKILLS`/`SCHEMA_TEMPLATES`). 구버전 설치본은
  기록된 schema로 검증한 뒤 재설치에서 managed exclude block만 교체하는 방식으로 업그레이드
  하고, 제거도 구버전 원장 그대로 지원한다.
- 자세한 출처·신뢰도 판정은 `docs/research/harness-engineering.md`에 기록한다.

## 4. 실행 방법

```bash
# 설치 / 기존 프로젝트 편입
./bootstrap.sh <git-project>
./bootstrap.sh --adopt <git-project>

# 읽기 전용 검사
./bootstrap.sh --diff <git-project>
./bootstrap.sh --doctor <git-project>

# 안전한 제거
./bootstrap.sh --uninstall <git-project>

# 저장소 테스트
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

실제 CLI 옵션과 검증 기준은 `README.md`와 `GETTING-STARTED.md`를 함께 갱신한다.

## 5. 데이터·산출물·보안

| 경로 | 소유자 | Git 정책 |
|---|---|---|
| 이 저장소의 `payload/`, `scripts/`, docs, tests | agent-project-kit | 추적 |
| 대상 worktree의 킷 어댑터·state | 설치 manifest | `info/exclude`, commit/push guard |
| 대상 `$GIT_COMMON_DIR/agent-project-kit/` | 설치 manifest | worktree 밖, 로컬 전용 |
| 대상의 `AGENTS.md`·`CLAUDE.md` (셋업 스킬이 승인 하에 생성·병합) | 사용자 프로젝트 | 추적·commit 허용 |
| 대상의 기존 지침·설정·소스 | 사용자 프로젝트 | 무단 수정 금지 |
| 토큰·키·개인정보 | 사용자 | 외부 업로드·추적 금지 |

## 6. 외부 문서 맵

- 조사와 출처 판정: `docs/research/harness-engineering.md`
- 사용자 시작 절차: `GETTING-STARTED.md`
- 설계·보안 계약: `docs/architecture.md`
- 변경 이력: `docs/change-log/README.md`

## 7. 주의사항

- Codex의 `AGENTS.override.md`는 같은 디렉터리의 `AGENTS.md`에 합쳐지는 것이 아니라
  대체한다. 기존 지침 overlay 용도로 무조건 생성하지 않는다.
- linked worktree에서 `.git`은 디렉터리가 아닌 파일일 수 있다. `git rev-parse` 결과를 쓴다.
- `core.hooksPath`를 단순 교체하면 Husky·pre-commit 등 기존 훅이 비활성화될 수 있다.
- `extensions.worktreeConfig`의 worktree scope는 local scope보다 우선하므로 두 값을 함께 검사한다.
- `info/exclude`는 공통 Git dir에 있으므로 linked worktree 간 영향 범위를 doctor에서 확인한다.
- bare+linked 구성의 local-scope hook 설치는 서버 hook 영향을 피하려고 거부한다.
- 부모 디렉터리는 파일 allowlist 밖이므로 rollback/uninstall에서 자동 삭제하지 않는다.
- 도구의 trust/managed policy가 프로젝트 훅을 비활성화할 수 있다. Git guard를 독립 방어로 둔다.

## 8. 현재 TODO

- [x] local-only installer와 소유권 manifest 구현 완료
- [x] Claude/Codex 공통 스킬·handoff·hook 어댑터 완료
- [x] 신규/기존/linked-worktree/격리/uninstall 전체 테스트 70개 통과
- [x] README·architecture·change-log 현행화
- [x] Claude Code와 Codex 실제 로딩 smoke test의 미검증 범위 기록
- [x] GitHub 저장소를 `bolero2/agent-project-kit`으로 rename
- [x] 공유 지침 문서 라이프사이클: 템플릿 배포 + init 인터뷰 생성 + adopt 병합 개편 절차
- [x] 사용자 스킬 팬아웃(`agent-kit-skill-sync`)과 Agent 도구 레지스트리(CONTEXT)
- [x] manifest schema v1→v2 업그레이드 경로와 회귀 테스트 78개 통과
- [ ] init 인터뷰·adopt 병합·skill-sync의 실제 Claude Code/Codex 대화형 smoke test
- 릴리스 단계에서 repository-local `bolero2` author로 `master`에 commit/push하고 CI를 확인한다.

## 9. 환경

- 기준 개발 환경: macOS/Linux, zsh/Bash, Git 2.31+, Python 3.10+ stdlib
- 현재 기본 브랜치: `master`
- GitHub 소유 계정: `bolero2`
- 최종 커밋 전 repository-local author를 `bolero2`로 확인한다.
