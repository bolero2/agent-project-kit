# 하네스 엔지니어링 조사와 설계 근거

> 조사일: 2026-07-22
> 목적: `agent-project-kit`의 기능을 유행어나 단일 사례가 아니라 검증 가능한 도구 계약과
> 반복 관찰된 엔지니어링 원칙에 연결한다.

## 1. 조사 방법

자료는 다음 순서로 신뢰한다.

1. **도구·프로토콜 공식 문서** — 파일 탐색 순서, 훅 동작, Git ignore처럼 구현 정확성이
   필요한 사실의 기준이다.
2. **제작사 엔지니어링 글** — 해당 조직의 실제 운영 사례로는 유효하다. 다만 생산성 수치와
   성공 조건은 그 조직의 자체 보고이며 일반 법칙으로 확대하지 않는다.
3. **독립 실무자의 상세 경험과 기술 해설** — 여러 1차 자료를 연결하는 데 유용하지만
   개인 경험 또는 해석임을 표시한다.
4. **마케팅 글·튜토리얼·프로젝트 README** — 용어와 아이디어 탐색에만 사용하고, 중요한
   계약은 공식 문서로 재확인한다.

서로 충돌할 때는 더 구체적인 공식 사양과 직접 실측을 우선한다. 출처가 없는 수치,
독립 재현이 없는 벤치마크, 특정 제품의 기능을 전체 에이전트 생태계의 표준처럼 표현한 문장은
설계 근거로 사용하지 않는다.

## 2. 교차검증으로 남은 핵심 원칙

### 2.1 하네스는 프롬프트 묶음이 아니라 피드백 시스템이다

Martin Fowler의 정리는 하네스를 에이전트에 방향을 주는 **가이드**와 결과를 감지하는
**피드백**의 결합으로 설명한다. OpenAI 사례도 짧은 저장소 안내, 구조화된 문서, 테스트·린트,
애플리케이션 로그와 UI 관측을 함께 사용한다. 따라서 이 킷은 지침 파일만 설치하지 않고
로컬 상태, 검증 절차, Git 가드를 한 시스템으로 취급한다.

### 2.2 루트 지침은 짧은 지도여야 한다

OpenAI는 `AGENTS.md`를 전체 지식 저장소가 아니라 약 100줄의 목차로 운영하고 상세 지식은
구조화된 문서로 옮긴 사례를 설명한다. Anthropic의 컨텍스트 엔지니어링 글도 필요한 정보를
필요한 순간에 가져오고, 컨텍스트에는 고신호 토큰만 남길 것을 권한다. Claude Code와 Codex의
공식 문서 모두 계층형 지침과 스킬의 점진적 로딩을 제공한다.

적용 원칙:

- 시작 시 공통 규칙과 최신 handoff만 읽는다.
- 긴 절차는 호출할 때만 읽는 스킬로 둔다.
- 과거 완료 내역은 활성 TODO에서 분리한다.
- 같은 규칙을 Claude용과 Codex용으로 따로 작성하지 않는다.

### 2.3 긴 작업에는 세션 밖의 내구성 있는 상태가 필요하다

Anthropic의 장기 실행 실험은 세션 압축만으로는 작업 연속성이 충분하지 않았고, 진행 상태,
실패·미검증 항목, 다음 작업과 Git 기록을 다음 세션이 읽을 수 있게 남겼을 때 개선됐다고
보고한다. 이 결과는 제한된 실험 환경의 관찰이므로 특정 파일 형식까지 일반화하지 않는다.
다만 서로 다른 도구가 교대하는 이 프로젝트에는 다음 최소 handoff 필드가 직접 필요하다.

- 현재 목표와 완료 조건
- 완료 작업과 남은 작업 1~3개
- 결정과 근거
- 변경 파일, 브랜치, HEAD, dirty 상태
- 실행한 검증 명령과 성공·실패·미실행 구분
- blocker와 다음 에이전트의 첫 행동

### 2.4 결정적 검사와 추론적 리뷰를 구분한다

테스트, 타입 검사, 린트, 포맷, staged path 검사는 동일 입력에 반복 가능한 신호를 준다.
설계 적절성이나 UX 평가는 모델 또는 사람의 판단이 필요하다. 둘을 모두 “검증”이라고 부르면
신뢰도가 사라진다. 킷의 handoff와 보고 규칙은 관측 사실·추론·미확인을 분리하고, 가능한
항목은 작은 결정적 검사로 먼저 확인한다.

### 2.5 효율은 모델을 크게 쓰는 것보다 불필요한 컨텍스트와 반복을 줄이는 데서 나온다

Anthropic은 단순한 에이전트 루프에서 시작해 측정된 실패가 있을 때만 복잡성을 추가하고,
도구 출력은 토큰 효율적으로 설계하라고 권한다. 장기 실행용 다중 에이전트 구조도 비용이 매우
높았으며 모델이 개선되면 일부 계층은 제거할 수 있다고 명시한다. 따라서 이 킷은 모델명을
고정하지 않고 다음 정책을 사용한다.

- 탐색·기계적 검사는 저비용 작업으로 분리한다.
- 고난도 설계·모호한 판단에만 강한 모델과 긴 추론을 사용한다.
- 반복 실패가 관찰되기 전에는 에이전트 계층을 추가하지 않는다.
- 전체 로그 대신 실패 요약과 재현 명령을 handoff에 남긴다.
- 완료 기록은 압축하고 현재 목표·다음 행동을 우선한다.

### 2.6 이식성은 공통 코어와 공식 탐색 경로의 얇은 어댑터로 만든다

Claude Code는 프로젝트의 `CLAUDE.md`/`CLAUDE.local.md`, `.claude/skills`, 프로젝트 설정과
훅을 읽는다. Codex는 `AGENTS.md` 계층, `.agents/skills`, 프로젝트 설정과 훅을 읽는다.
두 도구가 같은 파일명을 모두 해석하는 것은 아니다. Open Agent Skills 규격의 `SKILL.md`
형식은 공통 분모로 사용할 수 있다.

적용 원칙:

- 규칙·handoff·스킬 본문은 한 벌만 유지한다.
- 도구별 파일은 공통 코어를 가리키거나 동일 payload에서 생성한다.
- 같은 이름의 스킬 우선순위도 도구마다 다르다. Claude Code의 enterprise/personal/project
  순서와 Codex의 중복 노출 동작 때문에 “local이 global을 항상 override”한다고 가정하지 않는다.
- Codex의 `AGENTS.override.md`는 같은 디렉터리의 `AGENTS.md`를 대체하므로 기존 프로젝트
  지침 위에 단순 overlay하는 용도로 사용하지 않는다.
- Claude의 로컬 설정과 Codex 프로젝트 훅이 이미 존재하면 덮어쓰지 않고 충돌로 보고한다.

### 2.7 “커밋되지 않음”은 여러 층으로 방어하되 절대 보장처럼 말하지 않는다

Git 공식 문서는 저장소에만 적용되고 공유할 필요가 없는 패턴을
`$GIT_COMMON_DIR/info/exclude`에 둘 수 있다고 설명한다. 그러나 ignore는 이미 추적된 파일에
효력이 없고 `git add -f`로 우회할 수 있다. Git 훅도 `--no-verify` 또는 설정 변경으로 우회할
수 있다.

따라서 정상적인 사용자·에이전트 경로의 보장 범위는 다음 층으로 구성한다.

1. 정확한 root-anchored `info/exclude` 패턴으로 일반 `git add -A`를 예방한다.
2. pre-commit에서 staged tree의 킷 소유 경로를 차단한다.
3. pre-push에서 전송될 커밋의 킷 소유 경로를 다시 차단한다.
4. doctor가 exclude, manifest, 훅, 추적 상태의 드리프트를 감지한다.
5. 기존 프로젝트의 `.gitignore`와 추적 파일은 수정하지 않는다.

권한을 가진 사용자가 force-add와 모든 훅 우회를 고의로 함께 사용해도 불가능하다는 주장은
하지 않는다. 그런 강제 정책이 필요하면 원격 저장소의 CI·branch protection·서버 측 검사를
별도로 운영해야 한다.

## 3. 제공 자료의 판정

| 자료 | 유용한 부분 | 한계와 판정 |
|---|---|---|
| OpenAI Harness Engineering | 짧은 지도, 구조화된 문서, agent-legible 관측·검증 루프 | 1M LOC·1,500 PR·기간 수치는 OpenAI 내부 자체 보고다. 일반 생산성 보장으로 사용하지 않는다. |
| Channel Talk 글 | control·monitoring·feedback 관점의 쉬운 개요 | 2차 해설이며 제품·서비스 맥락이 섞인다. 구현 계약의 출처로 쓰지 않는다. |
| Select Star 글 | 컨텍스트·툴·검증·운영 요소의 요약 | 2차 해설이다. 공식 도구 동작은 원문으로 재확인한다. |
| WikiDocs 페이지 | 한국어 입문용 용어 정리 | 집필 중인 3차 자료다. “공식화된 용어” 같은 표현은 뒷받침할 1차 근거가 없어 채택하지 않는다. |
| revfactory/harness README | 다양한 하네스 패턴과 체크리스트 탐색 | 저장소 자체 README와 자체 테스트 수치다. 독립 평가나 범용 벤치마크로 간주하지 않는다. |
| Mitchell Hashimoto의 경험담 | 계획/실행 분리, 검증 가능한 작업, 반복 실패를 지침·도구 개선으로 환류 | 개인 경험이다. 저자도 보편적으로 합의된 용어라고 주장하지 않는다. |

## 4. 설계 추적성

| 구현 결정 | 근거 |
|---|---|
| 짧은 startup context + 상세 스킬 | OpenAI의 저장소 지도, Anthropic의 context engineering, 양 도구의 skill progressive disclosure |
| 공통 `HANDOFF.md` | Anthropic 장기 실행 실험 + Claude↔Codex 교대 요구 |
| 공통 skill payload와 두 탐색 어댑터 | Open Agent Skills 사양 + Claude/Codex 공식 skill 경로 |
| 기존 `AGENTS.md`/`CLAUDE.md` 무수정 | 프로젝트 고유 지침 보존 + Codex override 탐색 규칙 |
| `info/exclude` + pre-commit + pre-push + doctor | Git 공식 ignore/hook 한계와 대상 프로젝트 커밋 격리 요구 |
| 모델 비고정·측정 기반 복잡성 | Anthropic의 단순 루프·평가 기반 확장 원칙 |

## 5. 읽은 자료

### 1차·공식

- [OpenAI — Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- [Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic — Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [Claude Code — memory and project instructions](https://code.claude.com/docs/en/memory)
- [Claude Code — settings](https://code.claude.com/docs/en/settings)
- [Claude Code — skills](https://code.claude.com/docs/en/skills)
- [Claude Code — hooks](https://code.claude.com/docs/en/hooks-guide)
- [Codex — AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex — skills](https://learn.chatgpt.com/docs/build-skills)
- [Codex — hooks](https://learn.chatgpt.com/docs/hooks)
- [Open Agent Skills specification](https://openagentskills.dev/specification)
- [Git — gitignore](https://git-scm.com/docs/gitignore)
- [Git — githooks](https://git-scm.com/docs/githooks)

### 해설·사례

- [Martin Fowler — Harness Engineering](https://martinfowler.com/articles/harness-engineering.html)
- [Mitchell Hashimoto — My AI adoption journey](https://mitchellh.com/writing/my-ai-adoption-journey)
- [Channel Talk — 하네스 엔지니어링이란?](https://channel.io/kr/blog/articles/what-is-harness-2611ddf1)
- [Select Star — Harness Engineering](https://selectstar.ai/blog/insight/about-harness-engineering/)
- [WikiDocs — Harness Engineering](https://wikidocs.net/340857)
- [revfactory/harness — README_KO](https://github.com/revfactory/harness/blob/main/README_KO.md)

## 6. 아직 검증하지 않은 것

- Claude Code와 Codex 실제 제품 UI에서의 설치 후 end-to-end 로딩은 자동 테스트만으로 완전히
  대체할 수 없다. 릴리스 전 각 도구에서 smoke test가 필요하다.
- 프로젝트 trust/managed policy가 훅을 제한하는 조직 환경은 각 조직 정책에 따라 다르다.
- 여러 운영체제의 symlink·파일 권한 동작은 CI 매트릭스가 없는 플랫폼에서는 미검증이다.
- 하네스가 개발 속도나 품질을 몇 퍼센트 개선한다는 범용 수치는 이 조사로 입증되지 않았다.
