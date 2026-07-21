# claude-project-kit — 새 프로젝트 Claude Code 부트스트랩

> **전체 시작 절차는 [GETTING-STARTED.md](GETTING-STARTED.md) 참고** (Phase 0~3 체크리스트)

새 프로젝트 시작 시 이 킷을 복사하면, 매번 "이건 규칙으로 추가해줘"를 반복하지 않아도 된다.

## 사용법 (새 프로젝트에서)

```bash
# 1. 킷 복사
cp -r ~/claude-project-kit/CLAUDE.md        <새프로젝트>/CLAUDE.md
cp -r ~/claude-project-kit/.claude          <새프로젝트>/.claude

# 2. Claude Code 실행 후 첫 명령
/claude-md-init     # → repo 탐색 + 인터뷰로 CLAUDE.md의 TBD를 채움
```

## 무엇이 어디에 (스코프 구분 — 중요)

| 파일 | 스코프 | 복사 필요? |
|---|---|---|
| `CLAUDE.md` (시드) | 프로젝트 | ✅ 매 프로젝트 복사 |
| `.claude/skills/_template/` | 프로젝트 | ✅ 복사 후 프로젝트 스킬 만들 때 참고 |
| `.claude/agents/commit-push.md` | 프로젝트 | ✅ 복사 (git 잡일 위임용) |
| `.claude/commands/claude-md-init.md` | **글로벌**(`~/.claude/commands/`에 이미 있음) | ❌ 불필요 (킷엔 백업용으로 포함) |

- **글로벌**(`~/.claude/`)에 있는 것은 모든 프로젝트에 자동 적용 → 복사 불필요.
- **프로젝트**(`<repo>/.claude/`, `<repo>/CLAUDE.md`)는 repo마다 복사. git에 커밋하면 팀원·다른 도구도 공유.

## 각 파일의 역할

1. **CLAUDE.md (시드)** — §0 RULE(정직성·재현명령어·갱신·보안)은 완성돼 있고, §1~9는 TBD.
   `/claude-md-init`이 채워준다.
2. **`/claude-md-init` 커맨드** — repo 탐색(구조·실행법) + 사용자 인터뷰(목표·제약·보안) → CLAUDE.md 완성.
3. **skills/_template** — 반복 작업이 생기면 즉시 스킬화하기 위한 템플릿.
   "같은 지시를 2번 이상 하게 되면 스킬로 만든다"가 원칙 (토큰 절약의 핵심).
4. **agents/commit-push.md** — git 커밋 잡일을 서브에이전트로 위임 (메인 대화 토큰 절약,
   민감파일 커밋 방지 규칙 내장).

## 운영 원칙 (킷 자체의 갱신)

- 프로젝트 진행 중 새로 확립된 **범용** 규칙/패턴은 이 킷에도 반영한다 (다음 프로젝트에서 재사용).
- 프로젝트-specific한 것(특정 도커 이미지, 특정 지뢰)은 킷이 아니라 그 프로젝트의 CLAUDE.md·스킬에만.
