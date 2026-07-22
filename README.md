# claude-project-kit — Claude Code 프로젝트 하네스

> **전체 시작 절차는 [GETTING-STARTED.md](GETTING-STARTED.md) 참고** (Phase 0~3 체크리스트)

프로젝트에 Claude Code 협업 하네스(규칙·안전망·문서 체계·반복 절차)를 한 번에 깐다.
새 프로젝트 부트스트랩부터, 진행 중인 프로젝트 편입, 세션 마무리, 하네스 유지보수까지
프로젝트 수명 전체를 다룬다. 매번 "이건 규칙으로 추가해줘"를 반복하지 않기 위한 킷이다.

## 목표와 비-목표

- **목표**: 프로젝트를 진행/관리할 때 필요한 것들(CLAUDE.md 시드, 권한 시드, 안전 훅,
  .gitignore, 스킬 골격, 커밋 위임, 세션 마무리 절차)을 한 번에 까는 **나만의 하네스**.
  프로젝트 스코프 자산만 다룬다.
- **비-목표**: Claude Code 기본 기능이나 글로벌(`~/.claude/`) 스킬·플러그인 생태계를
  덮어쓰거나 대체·정리하는 것. 글로벌 세팅은 킷 밖의 관심사다.

## 한눈에 — 무엇을 할 수 있나

| 시점 | 도구 | 하는 일 |
|---|---|---|
| **신규 시작** | `bootstrap.sh <경로>` → `/claude-md-init` | 하네스 설치(11파일, no-clobber) → repo 탐색+인터뷰로 CLAUDE.md 완성 |
| **기존 프로젝트 편입** | `bootstrap.sh --adopt` → `/kit-adopt` | 진행 중 프로젝트에 무손상 설치 + 기존 CLAUDE.md를 §0+§1~9로 재편(내용 보존) |
| **작업 중 (자동)** | 안전 훅 + 권한 시드 | `rm -rf`·`curl\|sh`·force push 차단, 비밀 파일 읽기 차단, 시크릿 커밋 검출 — 매번 자동 |
| **작업 중 (위임)** | commit-push 에이전트, `_template` | git 잡일을 haiku로 위임(토큰 절약), 반복 지시 2회째는 스킬로 박제 |
| **세션 마무리** | `/wrap-up` | §8(TODO) 현행화 → change-log 기록 → 범용 패턴 킷 역수출 점검 → 커밋 제안 |
| **유지보수** | `bootstrap.sh --diff` / `--doctor` | 킷과의 드리프트 확인(선별 반영) / 하네스 무결성 점검(§0·훅·시크릿 추적·change-log 공백) |

## 사용법 (새 프로젝트)

```bash
# 1. 킷 복사 — 스크립트가 자기 위치 기준으로 동작하므로 킷 체크아웃 경로 무관
<킷 체크아웃 경로>/bootstrap.sh <새프로젝트 경로>

# 2. 새 프로젝트에서 Claude Code 실행 후 첫 명령
/claude-md-init     # → repo 탐색 + 인터뷰로 CLAUDE.md의 TBD를 채움
```

- `bootstrap.sh`는 **이미 존재하는 파일을 절대 덮어쓰지 않는다**(SKIP 표시) — 재실행 안전.
- 스크립트 없이 수동 복사 시: `CLAUDE.md`, `.claude/`, `templates/gitignore`(→`.gitignore`)를 직접 복사.

## 기존 프로젝트 편입 (adopt)

이미 진행 중인 프로젝트(Claude Code로 개발해 왔더라도)를 하네스로 편입한다:

```bash
# 1. 기계적 편입 — 클린 트리 요구(HEAD가 롤백 지점), 기존 파일 무손상
<킷 체크아웃 경로>/bootstrap.sh --adopt <프로젝트 경로>
#    → 훅·권한 시드·스킬 추가 + 기존 .gitignore에 누락된 보안 패턴만 append

# 2. 의미적 편입 — 해당 프로젝트의 Claude Code 세션에서
/kit-adopt
#    → 기존 CLAUDE.md에 §0 삽입·기존 내용을 §1~9로 재배치(버리지 않음),
#      기존 settings.json 병합, §5-보안 대조
```

- 모든 변경은 **미커밋 상태**로 남는다 — `git status`/`git diff`로 검토 후 커밋.
- 기존 CLAUDE.md의 규칙이 §0과 충돌하면 스킬이 목록을 보여주고 사용자 결정을 받는다.

## 유지보수 (--diff / --doctor)

```bash
# 킷이 갱신된 뒤, 프로젝트와의 차이 확인 — 아무것도 수정하지 않음
<킷 체크아웃 경로>/bootstrap.sh --diff <프로젝트 경로>

# 하네스 무결성 점검 — §0 존재·settings/훅 상태·민감 파일 추적·change-log 최신성
<킷 체크아웃 경로>/bootstrap.sh --doctor <프로젝트 경로>   # 오류(❌) 시 exit 1
```

- `--diff`는 동기화 대상(`.claude/`)만 내용 비교(다른 파일은 unified diff, `+` = 킷 버전),
  채워지며 달라지는 파일(CLAUDE.md 등)은 존재만 확인한다. 차이/누락 있으면 exit 1.
- `--doctor`는 change-log가 마지막 커밋보다 오래되면 경고한다 — 하네스가 죽어가는
  첫 징후를 잡는 용도. 읽기 전용이라 킷 자신에게도 실행 가능.

## 구성 — 무엇이 대상 프로젝트로 가나

| 킷 파일 | 역할 | 복사 → 대상 경로 |
|---|---|---|
| `CLAUDE.md` (시드) | §0 RULE 완성 + §1~9 TBD | `CLAUDE.md` |
| `.claude/skills/claude-md-init/` | CLAUDE.md TBD 채우기 (repo 탐색 + 인터뷰) | 그대로 |
| `.claude/skills/kit-adopt/` | 진행 중 프로젝트를 하네스로 편입 (CLAUDE.md 재편·settings 병합) | 그대로 |
| `.claude/skills/wrap-up/` | 세션 마무리 — §8 현행화·change-log·역수출 점검·커밋 제안 | 그대로 |
| `.claude/skills/_template/SKILL.template.md` | 프로젝트 스킬 템플릿 — `SKILL.md`로 개명 전까지 비활성 | 그대로 |
| `.claude/agents/commit-push.md` | git 커밋 잡일 위임 (haiku, 민감파일 제외 내장) | 그대로 |
| `.claude/settings.json` | 권한 시드 + 훅 연결 (아래 참조) | 그대로 |
| `.claude/hooks/` | 안전 훅 2종 — 파괴 명령 차단(PreToolUse), 시크릿 커밋 검출(Stop) | 그대로 |
| `templates/gitignore` | .gitignore 베이스 — 비밀·데이터·모델 선차단 | `.gitignore` |
| `templates/change-log-README.md` | change-log 인덱스 스텁 | `docs/change-log/README.md` |
| `README.md` · `GETTING-STARTED.md` · `bootstrap.sh` · `docs/` | 킷 자체용 | (복사 안 됨) |

킷의 모든 자산은 **프로젝트 스코프**(`<repo>/.claude/`)다. git에 커밋하면 팀원·다른 세션이 공유한다.
글로벌(`~/.claude/`)의 개인 설정·플러그인·rules는 킷이 건드리지 않는다.

## 보안 — 3층 방어

**①`.gitignore`(예방) → ②권한 deny(읽기 차단) → ③안전 훅(실행/커밋 차단)** + CLAUDE.md §0-4(규칙).
임의 서브프로세스가 직접 파일을 여는 것까지는 못 막으므로 층을 겹친다.

권한 시드(`.claude/settings.json`):

| 구분 | 내용 | 이유 |
|---|---|---|
| allow | `git status/diff/log/show` (읽기 전용) | 매번 뜨는 승인 프롬프트 제거 |
| deny | `.env*`, `*.pem`, `id_rsa*`, `secrets/` **읽기 차단** | 비밀이 대화·로그로 새는 것 방지. Read deny 규칙은 Claude Code가 인식하는 `cat`/`head`/`tail` 등 Bash 읽기 명령도 차단한다 |
| deny | `git push --force` / `-f` | 원격 이력 파괴 방지. deny는 allow/ask보다 우선한다 |

안전 훅(`.claude/hooks/`, python3 필요):

- `block-dangerous-bash.py` (PreToolUse): `rm -rf` 계열(분리 플래그 `-r -f` 포함),
  `curl | sh`, force push 전 어순, `chmod 777`, DB 클라이언트의 `DROP` 을 토큰/정규식
  분석으로 차단 — deny 프리픽스 매칭이 놓치는 변형을 잡는다.
- `verify-no-secrets.sh` (Stop): 턴 종료 시 스테이징된 파일명(.env, *.pem, id_rsa* 등)과
  **인덱스 내용**(AWS/GitHub/Slack 키, 개인키 헤더)을 검사해 커밋 전에 잡는다.
  `.env.example`은 허용.

프로젝트 사정에 맞게 수정해서 쓴다. 개인용 `.claude/settings.local.json`은 Claude Code가
자동으로 git 제외 처리한다.

주의: 훅이 활성화되면 에이전트는 `rm -rf`를 쓸 수 없다 — 임시 정리는 `-f` 없이 `rm -r`.

## 다른 AI 도구와 병용 (AGENTS.md)

Claude Code는 `CLAUDE.md`를 읽으며 `AGENTS.md`를 직접 읽지 않는다 (공식 문서 기준).
AGENTS.md를 쓰는 도구(Codex 등)와 병용하려면 둘 중 하나:

- CLAUDE.md 첫 줄에 `@AGENTS.md` import (공식 권장 패턴)
- `ln -s AGENTS.md CLAUDE.md` symlink (단일 소스 유지)

## 운영 원칙 (킷 자체의 갱신)

- 프로젝트 진행 중 새로 확립된 **범용** 규칙/패턴은 이 킷에도 반영한다 (다음 프로젝트에서 재사용).
  `/wrap-up`이 세션마다 역수출 후보를 보고한다.
- 킷을 갱신했으면 기존 프로젝트에는 `bootstrap.sh --diff`로 차이를 확인해 **선별 반영**한다
  (자동 덮어쓰기 없음).
- 프로젝트-specific한 것(특정 도커 이미지, 특정 지뢰)은 킷이 아니라 그 프로젝트의 CLAUDE.md·스킬에만.
- 스택별 템플릿 등 확장은 **실전에서 2회 반복 확인된 것만** 승격한다 (킷 비대화 방지).
- **동기화 규칙**: 시드 `CLAUDE.md`의 §0을 수정하면 `.claude/skills/claude-md-init/SKILL.md`
  스켈레톤의 §0도 반드시 함께 수정한다 (둘은 동일해야 한다).
- 킷을 수정하면 `docs/change-log/`에 기록한다.
