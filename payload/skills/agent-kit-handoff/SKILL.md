---
name: agent-kit-handoff
description: Claude Code와 Codex 사이 또는 새 세션으로 전환할 수 있도록 최소 재현 가능한 HANDOFF를 갱신한다.
---

# Agent Kit Handoff

도구 전환, 세션 종료, 컨텍스트 한도 접근 전에 수행한다.

1. `.agent-project-kit/HANDOFF.md`를 현재 사실로 교체한다. 완료 이력을 끝없이 누적하지 않는다.
2. 다음 항목을 짧고 구체적으로 기록한다.
   - 갱신 시각과 출발 도구
   - branch, HEAD, working tree status
   - 현재 objective
   - 완료한 변경과 그 근거
   - 결정과 이유
   - changed paths
   - 복사 가능한 검증 명령 및 passed/failed/not_run 구분
   - blocker/risk와 정확한 다음 한 단계
3. 실패 로그는 핵심 오류와 재현 명령만 남긴다. 성공하지 않은 결과를 성공으로 정리하지 않는다.
4. 비밀·개인정보·긴 대화 내용은 기록하지 않는다.
5. `git status --short`로 하네스 로컬 파일이 commit 후보에 나타나지 않는지 확인한다.

받는 도구는 기존 프로젝트 지침, CONTEXT, HANDOFF 순으로 읽고 현재 Git 상태와 어긋나는 요약은 실제 상태로 교정한다.
