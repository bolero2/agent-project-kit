---
name: agent-kit-init
description: 신규 프로젝트에서 사용자 인터뷰로 AGENTS.md와 포인터 CLAUDE.md를 만들고, 로컬 하네스 CONTEXT와 첫 HANDOFF를 증거 기반으로 초기화한다.
---

# Agent Kit Init

새 프로젝트에서 다음 순서로 수행한다.

1. 기존 `AGENTS.md`, `CLAUDE.md`, README, build/test 설정과 최상위 구조를 읽는다.
   두 파일 중 하나라도 이미 있으면 이 스킬 대신 `agent-kit-adopt`의 병합 절차를 따른다.
2. 사용자를 인터뷰해 프로젝트의 큰 그림을 확보한다. 최소한 다음을 묻는다.
   - 이 프로젝트가 해결하는 문제와 목표
   - 주요 기술 스택과 실행 환경
   - 성공 기준과 제약 조건
   - 사용할 Agent 도구 (기본: Claude Code, Codex — 그 외 도구는 이름과 지침 파일 규약을 물어 추가)
3. `.agent-project-kit/templates/AGENTS.template.md`를 기반으로 `AGENTS.md` 초안을 만들고,
   `CLAUDE.template.md` 기반의 포인터 `CLAUDE.md`와 함께 사용자에게 보여 승인을 받은 뒤
   저장소 루트에 생성한다.
   - 실제 규칙은 `AGENTS.md`에만 적는다. `CLAUDE.md`에는 `AGENTS.md` 참조 지침 외에 내용을 넣지 않는다.
   - 세부 규칙 항목은 미리 채우지 말고 TBD로 남긴다. 프로젝트를 진행하며 `AGENTS.md` 기준으로 갱신한다.
   - 두 파일은 공유 가능한 정보성 문서로 commit 대상이다. 사용자 승인 없이 생성·수정하지 않는다.
   - commit 금지 범위를 템플릿의 경계 그대로 적는다: 킷 로컬 파일만 금지하고, 사용자 스킬을
     포함한 `.claude/`·`.agents/` 전체를 커밋 금지로 일반화해 적지 않는다.
4. 실행하지 않은 명령을 성공했다고 쓰지 않는다. 사실·추론·미확인을 구분한다.
5. `.agent-project-kit/CONTEXT.md`의 `프로젝트 로컬 메모`만 짧게 갱신한다.
   - 목표 한 문장
   - 선언된 Agent 도구 목록
   - 실제로 확인한 실행/테스트 앵커
   - 작업에 필요한 중요 경로
   - 비밀·개인정보·생성물 경계
   - 확인된 지뢰
6. `.agent-project-kit/HANDOFF.md`에 branch/HEAD/status와 첫 다음 행동을 기록한다.
7. `git status --short`로 결과를 확인한다. 새로 만든 `AGENTS.md`/`CLAUDE.md`는 untracked로
   보이는 것이 정상이고, 로컬 킷 파일은 표시되지 않아야 한다.

사용자 승인 없이 프로젝트가 소유한 기존 tracked 문서나 설정을 수정하지 않는다. 세부 내용을 미리 모두 읽지 말고 현재 작업에 필요한 문서만 점진적으로 연다.
