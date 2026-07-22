# agent-project-kit — local Codex adapter

이 파일과 `.agent-project-kit/`은 이 저장소에만 설치된 로컬 하네스다. Git에 추가하지 않는다.

1. 저장소 루트에 `AGENTS.md`가 있으면 **먼저 직접 읽고 그 프로젝트 지침을 준수한다.**
2. `.agent-project-kit/CONTEXT.md`를 읽고 현재 프로젝트의 검증·효율 규칙을 따른다.
3. `.agent-project-kit/HANDOFF.md`에서 직전 도구/세션의 완료·실패·다음 작업을 확인한다.
4. 도구를 바꾸거나 세션을 끝내기 전 `agent-kit-handoff` 스킬로 HANDOFF를 갱신한다.

이 overlay는 프로젝트의 기존 지침을 대체하기 위한 것이 아니라, Codex가 공통 로컬 상태를 발견하게 하는 얇은 부트스트랩이다.
