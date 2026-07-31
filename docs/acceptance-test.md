# 수동 수용 테스트 가이드 (acceptance test)

이 문서는 킷을 설치한 뒤 실제 사용 흐름이 요구사항대로 동작하는지 사람이 검증하는 절차다.
자동 회귀 테스트(`python3 -m unittest discover -s tests`)가 이미 덮는 범위와, 사람이 판정해야
하는 대화형 범위를 구분해 기술한다.

| 시나리오 | 판정 방식 | 자동 테스트 커버 |
|---|---|---|
| A. 설치 격리 | 기계(명령 exit/출력) | 커버됨 (재확인용) |
| B. init 인터뷰 + 문서 생성 | 사람 | 미커버 — 수동 필수 |
| C. commit/push 차단 | 기계 | 커버됨 (재확인용) |
| D. adopt 병합 개편 | 사람 | 미커버 — 수동 필수 |
| E. 사용자 스킬 팬아웃 | 사람 + diff | 미커버 — 수동 필수 |
| F. handoff 왕복 | 사람 | 미커버 — 수동 필수 |
| G. 제거 | 기계 | 커버됨 (재확인용) |
| H. review-killer Agent 가동 | 사람 | 미커버 — 수동 필수 |
| I. developer Agent 가동 | 사람 | 미커버 — 수동 필수 |

전제: macOS/Linux, Git 2.31+, Python 3.10+, Claude Code와(또는) Codex 사용 가능.
아래 `KIT`은 이 저장소의 절대 경로다.

## A. 설치 격리 (기계 판정)

```bash
mkdir -p ~/tmp/apk-test && git -C ~/tmp/apk-test init
"$KIT/bootstrap.sh" ~/tmp/apk-test
git -C ~/tmp/apk-test status --short
"$KIT/bootstrap.sh" --doctor ~/tmp/apk-test; echo "doctor exit: $?"
```

- 성공: 설치 출력에 "설치 완료", `status --short` 출력이 **완전히 비어 있음**,
  doctor가 `OK: manifest/hash, ...` + exit 0.
- 실패: status에 킷 파일이 보이거나 doctor가 ERROR를 출력.

## B. init 인터뷰 + AGENTS.md/CLAUDE.md 생성 (사람 판정)

해당 프로젝트에서 Claude Code(또는 Codex)를 열고 요청한다.

```text
agent-kit-init 스킬로 프로젝트 인터뷰를 진행해서 AGENTS.md와 포인터 CLAUDE.md를 만들어 줘.
```

성공 기준 (모두 충족해야 함):

1. 에이전트가 문제/목표/기술 스택/성공 기준/사용할 Agent 도구를 **질문**한다.
2. 두 파일의 초안을 보여주고 **승인을 요청**한다. 승인 전에 파일을 쓰면 실패.
3. 생성된 `CLAUDE.md`는 `@AGENTS.md` 참조 지침 몇 줄뿐이고 실규칙이 없다.
4. `AGENTS.md`에 인터뷰 내용(큰 그림)이 반영되고 세부 규칙은 TBD로 남는다.
5. `git status --short`에 `AGENTS.md`/`CLAUDE.md`만 untracked로 보이고 킷 파일은 없다.
6. 두 파일을 `git add && git commit`하면 정상 커밋된다(guard가 막으면 실패).
7. `.agent-project-kit/CONTEXT.md`의 프로젝트 로컬 메모(목표, 선언된 Agent 도구 등)가 갱신된다.

## C. commit/push 차단 (기계 판정)

```bash
cd ~/tmp/apk-test
git add -A && git diff --cached --name-only        # 킷 경로 0개여야 함
git add -f CLAUDE.local.md && git commit -m x       # 차단되어야 함
git reset
```

- 성공: `add -A` 후 staged에 `.agent-project-kit/`·`CLAUDE.local.md`·`AGENTS.override.md`·
  `agent-kit-*` 경로가 0개. force-add 후 commit은 `차단됨 (pre-commit): 로컬 킷 경로 staged`
  메시지와 함께 실패(exit ≠ 0).
- 실패: 킷 경로가 커밋에 들어감.
- 참고: `git add -f` + commit/push 양쪽 `--no-verify` + hook 설정 변경을 고의로 조합한
  우회는 설계상 막지 않는다(실수 방지 계층이며 보안 경계가 아님).

## D. adopt 병합 개편 (사람 판정)

규칙이 이미 든 `CLAUDE.md`(또는 `AGENTS.md`)가 있는 기존 프로젝트를 준비하고:

```bash
"$KIT/bootstrap.sh" --adopt /path/to/existing-project
```

에이전트 세션에서:

```text
agent-kit-adopt 스킬로 편입하고, 기존 규칙을 AGENTS.md 기준 canonical+포인터 구조로
병합 개편안을 diff로 제시해 줘. 내 승인 없이 tracked 파일을 수정하지 마.
```

성공 기준:

1. 설치 자체는 기존 `AGENTS.md`/`CLAUDE.md`/`.gitignore`/dirty 상태를 바꾸지 않는다.
2. 병합 개편안이 **diff 형태로 먼저 제시**되고, 충돌·중복 항목은 사용자 선택으로 넘긴다.
3. 승인 후에만 규칙이 `AGENTS.md`로 이동하고 `CLAUDE.md`가 포인터로 교체된다.
4. 개편을 거부하면 기존 구조가 그대로 남고 그 사실만 CONTEXT에 기록된다.
- 실패: 승인 전에 tracked 파일이 수정됨, 또는 기존 규칙이 소실됨.

## E. 사용자 스킬 팬아웃 (사람 판정 + diff)

에이전트 세션에서 임의 스킬 생성을 요청한다.

```text
커밋 메시지를 정리해 주는 스킬을 만들어 줘.
```

성공 기준:

1. `.claude/skills/<이름>/SKILL.md`와 `.agents/skills/<이름>/SKILL.md`가 모두 생성된다.
2. `diff .claude/skills/<이름>/SKILL.md .agents/skills/<이름>/SKILL.md` 결과가 비어 있다.
3. 스킬 이름이 `agent-kit-`으로 시작하지 않는다.
4. commit 대상으로 둘지 로컬 전용으로 둘지 질문받는다.
5. 검증 중 만든 산출물이 정리된다(보존 요청이 없었다면).
6. 수정·삭제를 요청해도 두 경로에 동일하게 반영된다.

## F. handoff 왕복 (사람 판정)

Claude Code에서 작은 작업을 한 뒤:

```text
agent-kit-handoff 스킬로 지금 상태를 다음 도구에 넘길 수 있게 정리해 줘.
```

성공 기준:

1. `.agent-project-kit/HANDOFF.md`에 branch/HEAD/objective/완료 근거/검증
   (passed·failed·not_run)/다음 한 단계가 현재 사실로 채워진다.
2. 실행하지 않은 검증이 passed로 적히지 않는다.
3. 같은 프로젝트에서 Codex(또는 새 Claude Code 세션)를 열었을 때, 전체 맥락을 처음부터
   다시 설명하지 않아도 직전 작업을 이어간다. 세션 시작 시 HANDOFF 내용을 인지하고 있는지
   "지금 HANDOFF 내용이 뭐야?"로 확인할 수 있다.

## G. 제거 (기계 판정)

```bash
"$KIT/bootstrap.sh" --uninstall ~/tmp/apk-test; echo "exit: $?"
git -C ~/tmp/apk-test status --short
```

- 성공: exit 0, 킷 소유 파일(`.agent-project-kit/`, `CLAUDE.local.md`, `AGENTS.override.md`,
  `agent-kit-*` 스킬, provider hook 설정)이 사라지고, 사용자가 만든 `AGENTS.md`/`CLAUDE.md`/
  사용자 스킬/커밋 이력은 그대로 남는다. `info/exclude`와 hook 설정이 설치 전 상태로 복원된다.
- 실패: 사용자 파일이 삭제되거나, 킷 파일이 남거나, warning과 함께 중단(이 경우 사유를
  확인하고 정리 후 재시도 — 수정된 킷 파일이 있으면 의도적으로 전체 중단한다).

## H. review-killer Agent (사람 판정)

리뷰 봇이 붙어 있는 실제 저장소의 열린 PR에서:

```text
review-killer agent로 PR #<번호> 리뷰 처리해줘.
```

성공 기준:

1. 가동 직후 `AGENT-RULES.md`와 필수 문서를 읽고, CONTEXT에 리뷰봇 식별자/QA 방법이 없으면
   질문해 기록한다.
2. **가동 이전에 이미 올라온 리뷰**가 있으면 폴링 없이 즉시 처리부터 시작한다.
3. conflict가 있으면 리뷰 대기 전에 merge 방식으로 먼저 해소한다(force-push 없음 — reflog로 확인).
4. 리뷰 처리 라운드마다 PR 코멘트(수정/반박/보류 + 상태 마커)가 남고, 사용자 보고는 종료 시
   1회만 온다.
5. approve/수렴 시 "머지 가능합니다" 통보로 끝나고 **merge는 하지 않는다**. 수렴 판정 근거가
   최종 보고에 있다.
6. 30분(30초×40~60회) 동안 리뷰가 없으면 상태 코멘트를 남기고 종료한다.
- 실패: 리뷰를 무시하고 침묵, force-push, 자체 merge, PR 범위 밖 코드 수정, 거짓 수렴 선언.

## I. developer Agent (사람 판정)

Jira 보드가 연결된 프로젝트에서:

```text
developer agent로 작업 시작하자.
```

성공 기준:

1. 보드/담당자가 CONTEXT에 없으면 질문하고, 확인된 값을 CONTEXT에 기록한다.
2. 착수한 티켓에 잠금 코멘트("Agent가 처리 중")가 달리고, 이미 잠긴 티켓은 건드리지 않는다.
3. 티켓·사용자가 명시한 범위만 수정한다. 브랜치/커밋/PR 제목에 Jira 번호가 없다
   (PR description의 링크만 존재).
4. push/PR 전에 테스트(+가능하면 docker rebuild/run + Playwright QA)가 실행된다.
5. **commit/PR 생성 전 반드시 초안을 제시하고 승인을 기다린다.** 응답을 늦게 줘도 임의로
   진행하지 않는다.
6. 완료 시 잠금 코멘트를 삭제하고, 티켓 이동 목적지를 모르면 "어디로 옮길까요?"라고 묻는다.
- 실패: 무단 commit/PR, 잠금 없이 착수, Jira 번호 네이밍, 범위 외 수정, 임의 티켓 이동.

## 결과 기록

수행 결과는 전역 테스트 규칙에 따라 `docs/test/{YYYY-MM-DD}.md`에 기록한다. 각 시나리오의
통과/실패, 실제 출력 요지, 실패 시 원인 분석을 남기고, 대화형 시나리오(B/D/E/F)의 첫 실전
통과 여부는 `AGENTS.md` §8 TODO의 smoke test 항목에 반영한다.
