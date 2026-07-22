---
name: agent-kit-wrap-up
description: 세션을 증거 기반으로 마무리하고 다음 도구가 바로 이어갈 수 있게 상태를 압축한다.
---

# Agent Kit Wrap-up

1. 요청 범위의 변경과 `git diff --check`를 확인한다.
2. 위험에 비례한 테스트·lint·typecheck 중 실제로 필요한 검증을 실행한다.
3. 실패와 미실행 검증을 숨기지 않는다.
4. `agent-kit-handoff` 절차로 HANDOFF를 갱신한다.
5. staged 파일을 확인하고 로컬 하네스 경로와 비밀이 없는지 검증한다.
6. 커밋/푸시는 사용자의 권한과 프로젝트 절차가 있을 때만 수행한다.

CONTEXT에는 여러 세션에 재사용할 규칙만 승격한다. 일회성 결과와 완료 이력은 HANDOFF에도 장기 누적하지 않는다.
