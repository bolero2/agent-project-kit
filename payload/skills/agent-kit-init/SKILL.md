---
name: agent-kit-init
description: 새 Git 프로젝트의 로컬 하네스 CONTEXT와 첫 HANDOFF를 증거 기반으로 초기화한다.
---

# Agent Kit Init

새 프로젝트에서 다음 순서로 수행한다.

1. 기존 `AGENTS.md`, `CLAUDE.md`, README, build/test 설정과 최상위 구조를 읽는다.
2. 실행하지 않은 명령을 성공했다고 쓰지 않는다. 사실·추론·미확인을 구분한다.
3. `.agent-project-kit/CONTEXT.md`의 `프로젝트 로컬 메모`만 짧게 갱신한다.
   - 목표 한 문장
   - 실제로 확인한 실행/테스트 앵커
   - 작업에 필요한 중요 경로
   - 비밀·개인정보·생성물 경계
   - 확인된 지뢰
4. `.agent-project-kit/HANDOFF.md`에 branch/HEAD/status와 첫 다음 행동을 기록한다.
5. `git status --short`로 로컬 킷 파일이 표시되지 않는지 확인한다.

프로젝트가 소유한 tracked 문서나 설정을 하네스 초기화만을 위해 수정하지 않는다. 세부 내용을 미리 모두 읽지 말고 현재 작업에 필요한 문서만 점진적으로 연다.
