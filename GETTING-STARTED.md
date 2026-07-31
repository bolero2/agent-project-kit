# agent-project-kit 시작 가이드

이 가이드는 신규 프로젝트 setup, 진행 중인 프로젝트 편입, Claude Code ↔ Codex 전환,
진단과 제거까지 한 흐름으로 설명한다.

## 0. 한 번만 준비

```bash
git clone git@github.com:bolero2/agent-project-kit.git
cd agent-project-kit
python3 --version
git --version
```

킷은 글로벌 설정을 설치하지 않는다. 각 대상 Git 프로젝트에 따로 실행한다.

## 1-A. 신규 프로젝트

### 1. Git 저장소 준비

```bash
mkdir -p /path/to/new-project
git -C /path/to/new-project init
```

이미 clone한 저장소라면 이 단계는 생략한다. 아직 Git 저장소가 아닌 디렉터리에는 킷을
설치하지 않는다. commit 격리를 검증할 기준이 없기 때문이다.

### 2. 설치

```bash
/path/to/agent-project-kit/bootstrap.sh /path/to/new-project
```

정상 종료 시 기존 project file이나 `.gitignore`가 setup 때문에 바뀌어서는 안 된다.

```bash
git -C /path/to/new-project status --short
/path/to/agent-project-kit/bootstrap.sh --doctor /path/to/new-project
```

킷 파일은 local exclude되므로 `git status`에 나타나지 않는다. 사용자가 설치 전에 가지고 있던
변경은 그대로 나타나는 것이 정상이다.

### 3. 첫 에이전트 세션

Claude Code 또는 Codex 중 편한 도구를 프로젝트 루트에서 연다.

```text
agent-kit-init 스킬을 사용해 줘. 프로젝트 인터뷰를 진행해서 AGENTS.md와 포인터 CLAUDE.md를
만들고, 저장소를 탐색해 CONTEXT.md와 첫 HANDOFF.md를 완성해 줘.
관측 사실, 추론, 미확인을 구분하고 실행하지 않은 검사는 미실행으로 남겨 줘.
```

에이전트가 인터뷰로 묻는 내용:

- 이 프로젝트가 해결하는 문제, 목표와 성공 기준
- 주요 기술 스택과 실행 환경, 제약 조건
- 사용할 Agent 도구 (기본: Claude Code, Codex — 그 외 도구는 이름과 규약을 물어 추가)

인터뷰 결과로 `AGENTS.md`(canonical 지침, 큰 그림 위주 — 세부 규칙은 진행하며 채움)와
`AGENTS.md`를 참조만 하는 포인터 `CLAUDE.md` 초안이 제시되고, 승인하면 저장소 루트에
생성된다. 이 두 파일은 공유 가능한 정보성 문서로 평소처럼 commit한다.

탐색으로 확인하는 내용(실행·테스트 명령, 민감 경로, 알려진 지뢰, 첫 작업과 검증 anchor)은
`.agent-project-kit/`의 local-only state에 들어간다. 킷 setup 파일 자체를 커밋으로 만들지
않는다.

## 1-B. 진행 중인 프로젝트 편입

### 1. 현재 상태 확인

```bash
git -C /path/to/existing-project status --short
git -C /path/to/existing-project rev-parse --show-toplevel
```

dirty/staged/untracked 변경이 있어도 설치기는 보존한다. 다만 현재 출력은 편입 후 비교할 수 있게
기억해 둔다.

### 2. 편입 설치

```bash
/path/to/agent-project-kit/bootstrap.sh --adopt /path/to/existing-project
```

설치기가 기존 `AGENTS.md`, `CLAUDE.md`, `.gitignore`, 프로젝트 tool config를 수정하면 실패다.
owned adapter 경로가 이미 사용 중이면 쓰기 전에 충돌로 중단하는 것이 정상이다.

### 3. 의미적 편입

```text
agent-kit-adopt 스킬을 사용해 기존 AGENTS.md/CLAUDE.md와 저장소 구조, 현재 Git 상태,
최근 결정, 실행·검증 방법을 읽고 local CONTEXT/HANDOFF에 편입해 줘.
기존 규칙이 있으면 AGENTS.md 기준 canonical+포인터 구조로 병합 개편안을 diff로 제시해 줘.
내 승인 없이 tracked 파일을 수정하지 마.
```

에이전트는 기존 두 파일의 규칙을 `AGENTS.md`로 모으고 `CLAUDE.md`를 포인터로 교체하는
개편안을 제시한다. 충돌·중복 항목은 임의로 지우지 않고 차이를 보고하며, 사용자가 선택·승인한
결과만 반영한다. 개편을 원하지 않으면 기존 구조를 그대로 두고 그 사실만 CONTEXT에 남긴다.
승인 하에 개편된 `AGENTS.md`/`CLAUDE.md`는 tracked 변경으로 보이는 것이 정상이다.

## 2. 평소 작업

세션 시작 시:

1. 공통 context와 최신 handoff를 읽는다.
2. branch, HEAD, dirty 상태를 실제 Git 명령으로 재확인한다.
3. handoff와 다르면 관측 결과를 우선하고 handoff를 정정한다.
4. 다음 작업 하나와 완료 조건을 확인한 뒤 구현한다.

작업 중:

- 결정적 테스트·타입·린트를 먼저 사용한다.
- 설계·UX처럼 판단이 필요한 검토는 결정적 검사와 구분한다.
- 전체 로그를 context에 붙이지 않고 실패 원인과 재현 명령을 남긴다.
- 반복 지시는 프로젝트 local skill 후보로 만들되 `agent-kit-*` 기본 스킬을 무심코 덮어쓰지
  않는다.
- 제품 코드를 commit할 때 킷 파일을 수동 force-add하지 않는다.

마무리할 때:

```text
agent-kit-wrap-up 스킬로 완료 이력을 압축하고, 검증 결과와 남은 작업을 최신화해 줘.
```

## 2-B. 커스텀 Agent 사용

킷은 두 개의 커스텀 Agent를 설치한다(Claude Code `.claude/agents/`, Codex `.codex/agents/`).
둘 다 **트리거 문구로만 가동**되고, 가동 직후 `AGENT-RULES.md`·필수 문서를 정독하며, 모호한
것은 반드시 질문하고 답을 받을 때까지 대기한다.

### review-killer — PR 리뷰 자동 처리

```text
review-killer agent로 PR #111 리뷰 처리해 줘.
```

- 가동 전 올라온 리뷰부터 처리하고, conflict가 있으면 merge 방식으로 먼저 해소한다.
- 30초×40~60회 폴링하며 리뷰와 blocker(conflict/CI)를 동시 감시한다. 처리 내역은 PR 코멘트에
  쌓고 사용자에게는 종료 시 1회만 보고한다.
- 수렴/approve 시 "머지 가능합니다"로 끝난다. **merge는 직접 하지 않는다.**
- 타임아웃(약 30분 리뷰 없음) 후에는 "리뷰 자동 처리 계속 진행해 줘"로 재개한다.
- 첫 가동 시 리뷰봇 식별자와 QA 방법을 물어보고 CONTEXT에 기억한다.

### developer — Jira 티켓 처리

```text
developer agent로 작업 시작하자.
```

- 보드/담당자를 명시하지 않으면 CONTEXT에 기억된 값을 쓰고, 없으면 물어본다.
- 착수한 티켓에 잠금 코멘트를 남기고, 완료 시 삭제 후 티켓을 이동한다(목적지 모르면 질문).
- 브랜치·커밋·PR 제목에 Jira 번호를 넣지 않는다(PR description 링크만).
- push/PR 전에 테스트와 QA(docker rebuild + Playwright, Python이면 pytest 필수)를 수행한다.
- **commit/PR 생성은 반드시 초안을 보여주고 승인을 기다린다.** 응답이 늦어도 임의로 진행하지
  않는다.

## 3. Claude Code에서 Codex로 넘기기

Claude Code 세션이 끝나기 전에:

```text
agent-kit-handoff 스킬로 Codex가 이어서 작업할 수 있게 정리해 줘.
```

확인:

```bash
git status --short
git rev-parse --short HEAD
```

같은 프로젝트에서 Codex를 열고:

```text
최신 agent-project-kit handoff를 읽고 Git 상태와 핵심 실패를 재확인한 뒤 Next 첫 작업을 계속해.
```

Codex는 `AGENTS.override.md`를 먼저 읽는다. 어댑터 지시에 따라 프로젝트의 기존 `AGENTS.md`가
있으면 그것도 명시적으로 읽고 함께 준수한다.

## 4. Codex에서 Claude Code로 넘기기

Codex에서 같은 `agent-kit-handoff` 스킬을 실행한다. 그다음 프로젝트에서 Claude Code를 열고:

```text
최신 agent-project-kit handoff와 프로젝트 지침을 읽고, Git 상태를 재확인한 뒤 계속해.
```

Claude Code의 `CLAUDE.local.md`가 공통 context를 import한다. 기존 `CLAUDE.md`도 원래 방식대로
유지된다.

## 5. 진단과 업데이트

### 읽기 전용 diff

```bash
/path/to/agent-project-kit/bootstrap.sh --diff /path/to/project
```

manifest 기준으로 누락, 내용 hash 차이, exclude/hook drift를 보여준다. 아무것도 수정하지 않는다.

### 종합 doctor

```bash
/path/to/agent-project-kit/bootstrap.sh --doctor /path/to/project
```

최소 확인 항목:

- manifest와 owned file hash
- exact `info/exclude`
- 킷 파일의 tracked/staged 여부
- Git dispatcher와 pre-commit/pre-push
- local/worktree `core.hooksPath`와 기존 hook chain 정보
- 선택된 Git config managed block의 bytes·mode와 Git lock 충돌
- Claude/Codex adapter와 skill parity
- 사용자 수정 또는 삭제된 파일

오류가 있으면 exit 1이다. 도구 trust 승인이나 조직 policy처럼 CLI가 확정할 수 없는 항목은
경고·수동 확인으로 남긴다.

### 킷 업데이트 후 재설치

```bash
git -C /path/to/agent-project-kit pull --ff-only
/path/to/agent-project-kit/bootstrap.sh /path/to/project
```

설치 당시 hash와 같은 owned 파일만 안전하게 갱신한다. 사용자가 수정한 파일이 있으면 보존하고
충돌을 보고한다. 먼저 `--diff`로 확인해도 된다.

## 6. 제거

```bash
/path/to/agent-project-kit/bootstrap.sh --uninstall /path/to/project
```

제거기는 먼저 전체 상태를 검사한 뒤 모두 안전할 때만 한 번에 제거한다.

- immutable owned 파일 hash, mutable state의 초기 baseline, managed exclude, hook 설정이 모두
  설치 기록과 같아야 한다.
- 하나라도 다르면 **어떤 파일·exclude·설정도 제거하지 않고** exit 1로 중단한다.
- 깨끗하면 owned 파일과 초기 상태를 제거하고 `info/exclude`의 원래 bytes·mode 및 기존
  local/worktree Git config의 원래 bytes·mode/비존재 상태를 복원한다.
- 대상의 기존 프로젝트 파일과 후속 Git 설정 변경은 덮어쓰지 않는다.
- 부모 디렉터리는 파일 allowlist의 소유 대상이 아니므로 자동 삭제하지 않는다. 제거 뒤 빈
  `.claude`/`.agents`/`.codex`/`.agent-project-kit` 하위 디렉터리가 남을 수 있다.

실제로 사용한 `CONTEXT.md`/`HANDOFF.md`는 보통 baseline과 다르므로 기본 uninstall이 안전하게
중단한다. 이 상태를 보존하려면 먼저 저장소 밖의 안전한 위치에 복사하고, 킷 payload의 초기
두 파일로 되돌린 뒤 uninstall을 다시 실행한다. 로컬 상태를 버릴지 명시적으로 결정하지 않은
채 삭제하지 않는다.

제거 후:

```bash
git -C /path/to/project status --short
git -C /path/to/project config --local --get core.hooksPath || true
git -C /path/to/project config --worktree --get core.hooksPath || true
```

중단 보고가 있으면 어떤 변경도 일어나지 않았으므로 내용을 검토한 뒤 보존·원복 여부를 정하고
다시 실행한다.

linked worktree도 대상이 될 수 있지만 같은 Git common dir에는 한 번에 한 worktree만 설치한다.
다른 worktree로 옮길 때는 현재 대상에서 handoff를 보존한 뒤 uninstall하고 새 worktree에
설치한다. 공통 exclude가 sibling에도 적용되므로 다른 live worktree에 킷 exact/reserved 경로의
사용자 파일이 있거나 worktree에 접근할 수 없으면 설치·제거가 안전하게 중단된다.

bare 저장소와 linked worktree가 함께 있고 local-scope hook을 공유하는 구성은 서버 훅 의미를
바꿀 수 있어 설치하지 않는다. 필요한 경우 먼저 다음처럼 worktree config를 활성화한 뒤 대상
linked worktree에 설치한다.

```bash
git -C /path/to/linked-worktree config extensions.worktreeConfig true
/path/to/agent-project-kit/bootstrap.sh /path/to/linked-worktree
```

기존 hook은 설치 당시 경로로 고정하지 않는다. dispatcher가 호출될 때 현재 branch의
`includeIf`까지 반영된 managed 값 직전 hook을 chain하므로 Claude/Codex 작업 중 branch를 바꿔도
해당 branch의 원래 hook 의미를 유지한다.

프로젝트 디렉터리 자체를 이동하거나 이름을 바꿀 때도 먼저 uninstall한다. 설치 원장이 절대
경로를 사용하므로, 설치된 채 이동하면 이전 위치를 자동 추측해 제거하지 않는다. 새 PC·원격
개발 환경·새 clone에는 ignored local 파일이 전달되지 않으므로 그 checkout에서 별도로 설치한다.

## 7. 자주 만나는 충돌

### “owned path already exists”

`AGENTS.override.md`, `CLAUDE.local.md`, `.codex/hooks.json`,
`.claude/settings.local.json`, `agent-kit-*` 스킬 또는 `.agent-project-kit/`을 다른 도구가 이미
사용 중이다. 설치기는 소유권을 추측하지 않는다.

1. 파일이 tracked인지 `git ls-files --error-unmatch <path>`로 확인한다.
2. 어느 도구가 만든 파일인지 확인한다.
3. 기존 동작을 보존하는 통합 방법을 사용자가 결정한다.
4. 경로를 명시적으로 정리한 뒤 다시 설치한다.

### “symlink component”

owned path 또는 부모가 symlink다. 대상 밖 파일을 덮어쓸 수 있어 설치하지 않는다. 실제 링크
목적을 확인하고 정상 디렉터리 구조에서 다시 시도한다.

### 설치 뒤 Codex hook이 실행되지 않음

Codex 프로젝트 trust와 hook hash 승인을 확인한다. 새 hash는 재승인이 필요할 수 있다. Git
pre-commit/pre-push guard는 별도 계층이므로 `--doctor`로 함께 확인한다.

### 설치 뒤 Claude hook이 실행되지 않음

조직의 managed settings가 project hook을 제한하는지 확인한다. local settings가 충돌하면
설치기는 원래 실패해야 하며 기존 파일을 덮어쓰지 않는다.

### 킷 파일을 force-add함

pre-commit이 차단하는 것이 정상이다. 다음처럼 index에서만 제거한다.

```bash
git restore --staged -- AGENTS.override.md CLAUDE.local.md .agent-project-kit
```

다른 owned path가 있으면 doctor 출력에 따라 함께 unstage한다. working file을 삭제할 필요는 없다.

## 8. 완료 체크리스트

- [ ] 신규 또는 adopt 설치가 exit 0
- [ ] 설치 전후 사용자 `git status --short` 동일
- [ ] `bootstrap.sh --doctor` 오류 0
- [ ] Claude Code에서 공통 context와 4개 스킬 확인
- [ ] Codex에서 기존 `AGENTS.md`, 공통 context, 4개 스킬 확인
- [ ] 최초 handoff에 목표·Git·검증·다음 행동 기록
- [ ] 테스트용 도구 전환 1회 수행
- [ ] 제품 commit에 킷 소유 경로 0 확인
- [ ] 실제 제품 UI의 trust/hook 승인 상태 확인

## 9. 보장하지 않는 것

- 고의적인 `git add -f` + 모든 `--no-verify` + hook 설정 변경까지 로컬에서 절대 차단
- 조직 managed policy 우회
- 프로젝트 고유 테스트·보안 정책의 자동 설계
- 특정 모델 또는 에이전트 구성의 생산성 향상 퍼센트
- 글로벌 스킬·플러그인 관리
- Windows 또는 네트워크 파일시스템의 file-lock 동작
- Git을 통해 다른 checkout으로 local context/handoff 자동 동기화

이 항목이 필요하면 원격 CI, branch protection, secret scanning, 조직 정책을 별도로 구성한다.
