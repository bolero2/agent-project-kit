# Agent Project Context (local-only)

> Claude Code와 Codex가 함께 사용하는 짧은 운영 인덱스다. 확인하지 않은 사실을 채우지 말고, 세부 내용은 프로젝트 문서를 필요할 때 읽는다.

## 시작 순서

1. 현재 요청과 저장소의 기존 `AGENTS.md`/`CLAUDE.md`/경로별 규칙을 확인한다.
2. `HANDOFF.md`에서 직전 세션의 증거·실패·다음 한 단계를 확인한다.
3. 관련 코드와 테스트만 점진적으로 읽고, 오래된 요약보다 현재 코드·명령 결과를 우선한다.

## 공통 규칙

- 관측 사실, 출처가 있는 사실, 추론, 미확인을 구분한다. 실행하지 않은 검증은 미실행이라고 쓴다.
- 근거 없는 추정으로 행동하지 않는다. 가설은 가장 작은 실험으로 검증한 뒤에만 사실로 승격한다.
- 모든 작업 보고에는 근거(실행 명령, 구체 수치, 로그·문서 출처)와 검증 결과를 붙인다.
- 가장 작은 유효 변경을 만들고, 위험에 비례한 가장 좁은 검증부터 실행한다.
- 긴 로그는 결론·실패 원인·재현 명령·검증 앵커만 HANDOFF에 남긴다.
- 반복 실패는 같은 명령을 무작정 되풀이하지 말고 가설과 검증 방법을 바꾼다.
- 프로젝트 문서(`AGENTS.md` 포함)를 작업 중 수정하는 것은 사용자 기능 변경이다. setup과 구분하고 사용자 요청·승인 범위에서만 수행한다.
- 민감정보를 대화, 명령 인자, URL, Git config, 추적 파일에 넣지 않는다.
- 명확한 기계적 작업에는 저비용 모델·도구를, 복합 설계·디버깅에는 강한 모델을 선택한다.

## 공유 지침 문서

- `AGENTS.md`가 canonical 프로젝트 지침이다. `CLAUDE.md`는 `AGENTS.md`를 가리키는 얇은 포인터로 유지하고 실제 규칙을 복제하지 않는다.
- 규칙 추가·변경은 `AGENTS.md`에만 반영한다. 두 파일은 공유 가능한 정보성 문서로 commit/push가 허용된다.
- 두 파일이 없으면 `agent-kit-init`(신규) 또는 `agent-kit-adopt`(기존 병합) 스킬의 인터뷰·승인 절차로 만든다. 템플릿: `.agent-project-kit/templates/`.

## 커스텀 Agent

- 설치된 Agent: `review-killer`(PR 리뷰 자동 처리), `developer`(Jira 티켓 처리). 공통 계약은
  `.agent-project-kit/AGENT-RULES.md`에 있고 Agent는 가동 직후 이를 정독한다.
- Agent는 사용자의 트리거 문구로만 가동한다 (예: "PR #111 리뷰 처리해줘", "작업 시작하자").
  세션 시작만으로 자동 가동하지 않는다.
- 공유 상태 문서 수정 시 `<파일명>.lock` 규약을 따른다: lock이 있으면 대기, 수정 시 lock 생성
  후 즉시 삭제.

## Agent 도구와 스킬

- 선언된 Agent 도구 목록은 아래 프로젝트 로컬 메모에 유지한다. 기본값은 Claude Code, Codex이며 그 외 도구는 사용자에게 물어본 뒤 추가하고, 그 도구용 지침 파일을 함께 만든다.
- 사용자 스킬의 생성·수정·삭제는 `agent-kit-skill-sync` 절차를 따른다: 선언된 모든 도구 경로에 동일 원본으로 반영하고, 동작 검증 후 검증 산출물은 삭제한다.
- 하네스 파일은 로컬 전용이다. `.agent-project-kit/`, `AGENTS.override.md`, `CLAUDE.local.md`, 설치된 `agent-kit-*` 스킬과 provider hook 설정을 stage/commit하지 않는다.
- 킷 guard는 실수 방지 보조 장치다. `git add -f`, `--no-verify`, hook 설정 변경 등의 우회를 권한 경계로 간주하지 않는다.

## 프로젝트 로컬 메모

- 목표: TBD
- 선언된 Agent 도구: Claude Code, Codex
- 실행/테스트 앵커: TBD
- 중요한 경로: TBD
- 보안/데이터 경계: TBD
- 반복해서 발생한 지뢰: TBD
- QA 방법 (Agent용): TBD
- 리뷰봇 식별자 (review-killer용): TBD
- Jira 보드/담당자 (developer용): TBD

프로젝트를 처음 탐색했다면 `agent-kit-init`, 진행 중 저장소를 편입했다면 `agent-kit-adopt` 스킬로 이 절만 간결하게 갱신한다.
