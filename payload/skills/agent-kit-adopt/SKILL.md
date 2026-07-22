---
name: agent-kit-adopt
description: 진행 중인 Git 프로젝트를 기존 tracked 파일 변경 없이 공통 로컬 하네스 상태로 편입한다.
---

# Agent Kit Adopt

진행 중 프로젝트의 현재 상태를 보존하며 편입한다.

1. `git status --short --branch`, 최근 커밋, 기존 agent 지침과 관련 작업 문서를 확인한다.
2. 변경 파일을 사용자 작업과 이번 세션 작업으로 임의 분류하지 않는다. 출처가 불명확하면 그대로 표시한다.
3. `.agent-project-kit/CONTEXT.md`에는 반복 사용할 안정적인 프로젝트 사실과 검증 앵커만 남긴다.
4. `.agent-project-kit/HANDOFF.md`에는 현재 목표, 완료 증거, 실패, dirty paths, 다음 한 단계를 남긴다.
5. 기존 `AGENTS.md`, `CLAUDE.md`, `.gitignore`, provider 설정을 자동 병합·재작성하지 않는다.
6. `git status --short`와 필요하면 installer `--doctor` 결과로 격리를 확인한다.

대화 전문, 긴 로그, 비밀, 곧 낡을 세부 구현은 기록하지 않는다.
