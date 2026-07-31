---
name: agent-kit-adopt
description: 진행 중인 Git 프로젝트를 공통 로컬 하네스 상태로 편입하고, 사용자 승인 하에 기존 AGENTS.md/CLAUDE.md를 canonical+포인터 구조로 병합 개편한다.
---

# Agent Kit Adopt

진행 중 프로젝트의 현재 상태를 보존하며 편입한다.

1. `git status --short --branch`, 최근 커밋, 기존 agent 지침과 관련 작업 문서를 확인한다.
2. 변경 파일을 사용자 작업과 이번 세션 작업으로 임의 분류하지 않는다. 출처가 불명확하면 그대로 표시한다.
3. 공유 지침 문서를 canonical+포인터 구조로 개편한다. 무단으로 수정하지 않는다.
   - `AGENTS.md`/`CLAUDE.md`가 모두 없으면 `agent-kit-init`의 인터뷰 절차로 생성한다.
   - 기존 규칙이 있으면 두 파일(및 다른 agent 지침 파일)의 내용을 읽고, 실제 규칙을 `AGENTS.md`로
     모으는 병합 개편안을 diff로 제시한다. 충돌·중복 항목은 임의로 지우지 말고 사용자가 선택하게 한다.
   - 사용자 승인 후에만 반영한다: 규칙은 `AGENTS.md`로 병합하고, `CLAUDE.md`는
     `.agent-project-kit/templates/CLAUDE.template.md` 기반 포인터로 교체한다.
   - 사용자가 개편을 원하지 않으면 기존 구조를 그대로 두고 그 사실만 CONTEXT에 기록한다.
4. 사용 중인 Agent 도구를 인터뷰로 확인해 CONTEXT의 `선언된 Agent 도구` 목록을 갱신한다.
   Claude Code/Codex 외 도구는 그 도구용 지침 파일 필요 여부를 함께 확인한다.
5. `.agent-project-kit/CONTEXT.md`에는 반복 사용할 안정적인 프로젝트 사실과 검증 앵커만 남긴다.
   갱신 전 `CONTEXT.md.lock` 규약을 따른다(lock이 있으면 대기, 갱신 시 생성 후 삭제).
6. `.agent-project-kit/HANDOFF.md`에는 현재 목표, 완료 증거, 실패, dirty paths, 다음 한 단계를 남긴다.
7. `git status --short`와 필요하면 installer `--doctor` 결과로 격리를 확인한다.
   승인 하에 개편한 `AGENTS.md`/`CLAUDE.md`는 tracked 변경으로 보이는 것이 정상이다.

대화 전문, 긴 로그, 비밀, 곧 낡을 세부 구현은 기록하지 않는다.
