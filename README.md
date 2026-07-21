# claude-project-kit — 새 프로젝트 Claude Code 부트스트랩

> **전체 시작 절차는 [GETTING-STARTED.md](GETTING-STARTED.md) 참고** (Phase 0~3 체크리스트)

새 프로젝트 시작 시 이 킷을 복사하면, 매번 "이건 규칙으로 추가해줘"를 반복하지 않아도 된다.

## 목표와 비-목표

- **목표**: 새 프로젝트를 구성할 때 필요한 것들(CLAUDE.md 시드, 권한 시드, .gitignore,
  스킬 골격, 커밋 위임)을 한 번에 까는 **나만의 하네스**. 프로젝트 스코프 자산만 다룬다.
- **비-목표**: Claude Code 기본 기능이나 글로벌(`~/.claude/`) 스킬·플러그인 생태계를
  덮어쓰거나 대체·정리하는 것. 글로벌 세팅은 킷 밖의 관심사다.

## 사용법 (새 프로젝트에서)

```bash
# 1. 킷 복사 — 스크립트가 자기 위치 기준으로 동작하므로 킷 체크아웃 경로 무관
<킷 체크아웃 경로>/bootstrap.sh <새프로젝트 경로>

# 2. 새 프로젝트에서 Claude Code 실행 후 첫 명령
/claude-md-init     # → repo 탐색 + 인터뷰로 CLAUDE.md의 TBD를 채움

# (선택) 킷이 갱신된 뒤, 기존 프로젝트와의 차이 확인 — 아무것도 수정하지 않음
<킷 체크아웃 경로>/bootstrap.sh --diff <프로젝트 경로>
```

- `bootstrap.sh`는 **이미 존재하는 파일을 절대 덮어쓰지 않는다**(SKIP 표시) — 재실행 안전.
- `--diff`는 동기화 대상(`.claude/`)만 내용 비교(다른 파일은 unified diff, `+` = 킷 버전),
  채워지며 달라지는 파일(CLAUDE.md 등)은 존재만 확인한다. 차이/누락 있으면 exit 1.
- 스크립트 없이 수동 복사 시: `CLAUDE.md`, `.claude/`, `templates/gitignore`(→`.gitignore`)를 직접 복사.

## 구성 — 무엇이 대상 프로젝트로 가나

| 킷 파일 | 역할 | 복사 → 대상 경로 |
|---|---|---|
| `CLAUDE.md` (시드) | §0 RULE 완성 + §1~9 TBD | `CLAUDE.md` |
| `.claude/skills/claude-md-init/` | CLAUDE.md TBD 채우기 (repo 탐색 + 인터뷰) | 그대로 |
| `.claude/skills/_template/SKILL.template.md` | 프로젝트 스킬 템플릿 — `SKILL.md`로 개명 전까지 비활성 | 그대로 |
| `.claude/agents/commit-push.md` | git 커밋 잡일 위임 (haiku, 민감파일 제외 내장) | 그대로 |
| `.claude/settings.json` | 권한 시드 (아래 참조) | 그대로 |
| `templates/gitignore` | .gitignore 베이스 — 비밀·데이터·모델 선차단 | `.gitignore` |
| `templates/change-log-README.md` | change-log 인덱스 스텁 | `docs/change-log/README.md` |
| `README.md` · `GETTING-STARTED.md` · `bootstrap.sh` · `docs/` | 킷 자체용 | (복사 안 됨) |

킷의 모든 자산은 **프로젝트 스코프**(`<repo>/.claude/`)다. git에 커밋하면 팀원·다른 세션이 공유한다.
글로벌(`~/.claude/`)의 개인 설정·플러그인·rules는 킷이 건드리지 않는다.

## 권한 시드 (.claude/settings.json)

| 구분 | 내용 | 이유 |
|---|---|---|
| allow | `git status/diff/log/show` (읽기 전용) | 매번 뜨는 승인 프롬프트 제거 |
| deny | `.env*`, `*.pem`, `id_rsa*`, `secrets/` **읽기 차단** | 비밀이 대화·로그로 새는 것 방지. Read deny 규칙은 Claude Code가 인식하는 `cat`/`head`/`tail` 등 Bash 읽기 명령도 차단한다 |
| deny | `git push --force` / `-f` | 원격 이력 파괴 방지. deny는 allow/ask보다 우선한다 |

한계: 임의 서브프로세스(예: 파이썬 스크립트가 직접 파일을 여는 경우)까지는 막지 못한다 —
`.gitignore`와 CLAUDE.md §0-4가 이중 방어. 프로젝트 사정에 맞게 수정해서 쓴다.
개인용 `.claude/settings.local.json`은 Claude Code가 자동으로 git 제외 처리한다.

## 다른 AI 도구와 병용 (AGENTS.md)

Claude Code는 `CLAUDE.md`를 읽으며 `AGENTS.md`를 직접 읽지 않는다 (공식 문서 기준).
AGENTS.md를 쓰는 도구(Codex 등)와 병용하려면 둘 중 하나:

- CLAUDE.md 첫 줄에 `@AGENTS.md` import (공식 권장 패턴)
- `ln -s AGENTS.md CLAUDE.md` symlink (단일 소스 유지)

## 운영 원칙 (킷 자체의 갱신)

- 프로젝트 진행 중 새로 확립된 **범용** 규칙/패턴은 이 킷에도 반영한다 (다음 프로젝트에서 재사용).
- 킷을 갱신했으면 기존 프로젝트에는 `bootstrap.sh --diff`로 차이를 확인해 **선별 반영**한다
  (자동 덮어쓰기 없음).
- 프로젝트-specific한 것(특정 도커 이미지, 특정 지뢰)은 킷이 아니라 그 프로젝트의 CLAUDE.md·스킬에만.
- **동기화 규칙**: 시드 `CLAUDE.md`의 §0을 수정하면 `.claude/skills/claude-md-init/SKILL.md`
  스켈레톤의 §0도 반드시 함께 수정한다 (둘은 동일해야 한다).
- 킷을 수정하면 `docs/change-log/`에 기록한다.
