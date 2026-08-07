---
name: agent-kit-jira-ticket
description: >
  QA/개발 중 발견한 결함(버그) 또는 미구현/해야 할 일(작업)을 Jira 티켓으로 만든다.
  증거 기반으로 only-frontend / only-backend / both(full-stack)를 판정하고 종류별 템플릿으로
  초안을 작성해, 사용자 승인 후에만 Atlassian MCP로 생성한다. "지라 티켓 만들어줘",
  "이 버그 티켓으로", "QA 결과 지라에 올려줘", "<보드 URL> 보드에 지라 티켓 만들어줘" 요청 시
  사용한다. 같은 목적의 마켓플레이스 스킬(jira-qa-ticket)이 설치되어 있으면 그것을 우선한다.
---

# Agent Kit Jira Ticket

같은 목적의 마켓플레이스 스킬(`jira-qa-ticket`, soln-va-tools 등)이 설치되어 있으면 **그것을
우선 사용하고 이 스킬은 쓰지 않는다** (킷의 soln-va-tools 우선 원칙).

## 절대 규칙 (다른 모든 규칙보다 우선)

외부 상태를 바꾸는 모든 Jira 호출(`createJiraIssue`, `createIssueLink`, `editJiraIssue`,
`transitionJiraIssue`, `addCommentToJiraIssue`)은 **사용자의 명시적 승인 없이 실행하지 않는다.**
조회 계열(`searchJiraIssuesUsingJql`, `getJiraIssue`, `getJiraProjectIssueTypesMetadata`,
`getAccessibleAtlassianResources`)은 자유. 티켓 1건 = 승인 1회가 기본이며, 사용자가 "여러 건
한꺼번에"라고 범위를 명시했을 때만 묶는다. 판정이 애매하면 추측하지 말고 묻는다.

순서: ① 증거 수집 → ② 판정 → ③ 초안 → ④ 초안 제시 → ⑤ **명시적 승인** → ⑥ 생성 → ⑦ 보고.

MCP 도구가 지연 로드 환경이면 필요한 도구를 **한 번의 ToolSearch로** 불러온다. 서버명
대소문자를 임의로 바꾸지 않는다.

## 설정 — `.agent-project-kit/jira-ticket.config.json`

조직 고유값(site/cloudId/projectKey/boardId/sprintFieldKey/defaultSprintId·Name)은 이 파일
한 벌에 둔다(Claude Code/Codex 공용, 재설치에도 보존됨). 이 SKILL.md 자신은 수정하지 않는다.

- 값이 비었으면 미설정. **우선순위: 이번 요청 명시 > config > 물어보기.**
- 이번 요청에만 지정된 값("이 티켓은 X 보드로")은 **파일에 쓰지 않는다.** "기억해라/앞으로도"가
  있을 때만 저장하고, 덮어쓸 때는 이전 값 → 새 값을 함께 보여준다.
- 최초 부트스트랩(미설정 시): 질문은 **보드 URL 하나**만 —
  `https://<사이트>/jira/software/projects/<KEY>/boards/<id>`에서 site/projectKey/boardId를
  파싱하고, cloudId는 site를 그대로 시도(거부 시 `getAccessibleAtlassianResources`).
  **`getJiraProjectIssueTypesMetadata`가 성공해야만 저장한다** — 검증 안 된 값을 남기지 않는다.
  무엇을 저장했는지 보고한다.
- 보드는 프로젝트의 필터 뷰다. `createJiraIssue`에 보드 id 파라미터는 없다 — 이슈는
  projectKey로 생성되고 보드 필터에 매칭되어 나타난다.

## 이슈 타입

증상이 있는 결함 = `버그`, 해야 할 일/미구현/개선 = `작업` (한글 로케일 — 타입명 한글 전달,
거부되면 `getJiraProjectIssueTypesMetadata`로 확인 후 재시도). 이 판정은 FE/BE/FS 판정과 직교.

## 스프린트 — 사고 다발 구간

- 🚨 **한글 값을 JQL 문자열로 쓰면 오류 없이 0건이 나온다.** `sprint`와 `status`는 반드시
  숫자 id로 조회한다. (`sprint = 10862` ✅ / `sprint = "DF MVP 스프린트 6"` ❌)
- 필드 key(`customfield_xxxxx`)와 활성 스프린트 id는 런타임에 해석한다: 최근 이슈 1건을
  조회해 sprint 커스텀 필드 배열(`{id, name, state, ...}`)에서 key와 `state: "active"`인 id를
  얻는다. 해석 실패 시 **추측 id 금지** — 묻거나, 스프린트 없이 생성 후 보고.
- 🚨 **저장된 defaultSprintId는 만료된다.** 매 실행 시 그 id로 이슈 1건을 조회해 `state`가
  active인지 확인하고, 아니면 저장값을 버리고 활성 스프린트를 재해석해 사용자 확인 후 config를
  갱신한다.
- 결정 순서: 이번 요청 지정 > config(만료 검사 통과 시) > 활성 스프린트 자동 해석(확인만 받음)
  > 질문. 임의 선택 금지.
- 🚨 `searchJiraIssuesUsingJql` 응답에는 description이 항상 포함되어 커질 수 있다 —
  `maxResults`(해석용은 1)와 `fields`로 좁히고, 넘치면 파일로 받아 `jq`로 슬라이스한다.
- 생성 시 `additional_fields: { "<sprintFieldKey>": <숫자 sprintId> }`.

## 판정과 증거

증거를 먼저 모은다: 재현 절차(번호), 기대 vs 실제, 네트워크 증거(HTTP status·페이로드 —
FE/BE 판정의 핵심), 로그, 데이터 상태. **증거 등급을 구분해 적는다**: 확인(직접 관측) /
대조(`경로:라인` 함께) / **추정("추정"이라고 명시)**. 실행하지 않은 검증을 통과로 쓰지 않으며,
원인 진단의 핵심이 추정이면 티켓 생성 전에 재현을 시도한다.

| 종류 | 기준 |
|---|---|
| 🟦 only-frontend | 관련 요청 전부 2xx + 페이로드 정상인데 증상이 렌더/state/캐시/라우팅/스타일/핸들러 |
| 🟥 only-backend | 4xx/5xx 또는 스키마·정합성·성능·권한 오류, FE 요청 자체는 정상 |
| 🟪 both (full-stack) | FE↔BE 계약 불일치 또는 양쪽 수정 필요 |

판정 근거를 제시하고 사용자 확인을 받는다. 증상이 하나여도 원인이 둘일 수 있다 — 원인이
독립이면 티켓을 나눈다(BE 응답 직접 호출이 가장 확실한 갈라내기). full-stack이면 구조를 묻는다:
독립 티켓 2건+`Relates` 링크(기본 추천) / 단일 티켓 / 부모+하위 작업.

## 본문 템플릿

Summary: `[BUG][FE|BE|FS] <간결한 증상>` — 원인·수정법을 제목에 넣지 않는다.

공통 골격: `## 재현 절차`(번호) / `## 기대 결과` / `## 실제 결과` / `## 제안 수정`(`파일:라인`)
+ 최하단 푸터 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
환경(브랜치/커밋)·관련 링크 섹션은 넣지 않는다.

종류별 추가 섹션 `## 분류: Frontend|Backend|Full-stack`: FE는 트리거·영향 컴포넌트·수정 위치와
**BE 응답이 정상이라는 증거**, BE는 엔드포인트·기대 vs 실제 스키마·`curl` 재현(토큰은 `<JWT>`
마스킹)·수정 위치, FS는 BE/FE 파트별 원인·수정 위치·계약 변경과 작업 순서·의존성. 티켓을 나눌
때는 각 본문에 "다른 쪽은 별건(<KEY>)"을 명시한다.

## 생성과 보고

- 생성 전 **중복 확인**: 활성 스프린트를 `summary,status` 필드로 검색해 유사 티켓이 있으면
  새로 만들지/기존에 코멘트 달지 확인.
- 초안 제시는 다섯 가지 전부: 대상(projectKey/보드) · 타입 · 스프린트(이름+숫자 id) ·
  Summary · **description 전문(푸터 포함)**. "이대로 생성할까요?"로 승인받는다.
- `createJiraIssue`: `contentFormat: "markdown"`. **`labels`는 절대 넣지 않는다.** priority·
  assignee는 사용자가 요청할 때만(assignee는 `lookupJiraAccountId` 확인값만). 생성 후 상태
  이동은 이 스킬 범위 밖(기본 "해야 할 일"로 생성됨).
- 관련 티켓 2건 이상이면 승인 범위 안에서 `createIssueLink`(`Relates`, 거부 시
  `getIssueLinkTypes` 확인).
- 보고: 이슈 키와 URL, 타입/스프린트/상태, 링크 관계, 실패·수동 조치 항목.
- 시크릿(토큰·Authorization 값·.env 값)을 본문에 넣지 않는다 — 넣기 전에 눈으로 확인한다.
- 검증 목적으로 만든 티켓은 반드시 정리한다(사용자 삭제 승인).
