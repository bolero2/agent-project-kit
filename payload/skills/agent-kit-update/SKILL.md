---
name: agent-kit-update
description: 설치된 킷 버전과 킷 저장소 원본(GitHub bolero2/agent-project-kit)의 최신 버전을 비교하고, 사용자 승인 하에 pull + 재설치로 업데이트한다.
---

# Agent Kit Update

하네스 업데이트 확인·적용 절차. 세션에서 하루 1회만 자동 수행하고, 사용자가 직접 요청하면
날짜와 무관하게 수행한다.

1. `.agent-project-kit/CONTEXT.md` 로컬 메모의 `킷 업데이트 마지막 확인`이 오늘 날짜면
   아무것도 하지 않고 원래 작업을 계속한다.
2. 설치 버전 확인:
   ```bash
   cat "$(git rev-parse --path-format=absolute --git-common-dir)/agent-project-kit/manifest.json" \
     | python3 -c "import json,sys; print(json.load(sys.stdin)['kit_version'])"
   ```
3. 킷 저장소 위치는 CONTEXT 로컬 메모의 `킷 저장소 경로`를 쓴다. 비어 있으면 사용자에게 물어
   기록한다. 로컬에 clone이 없으면 clone할 위치를 물어
   `git clone https://github.com/bolero2/agent-project-kit.git` 후 경로를 기록한다.
4. 최신 버전 확인 (킷 저장소는 수정하지 않는다):
   ```bash
   git -C <킷 경로> fetch origin master
   git -C <킷 경로> show origin/master:scripts/agent_project_kit.py | grep 'KIT_VERSION ='
   ```
   네트워크가 안 되면 확인을 건너뛰고 그 사실만 보고한 뒤 작업을 계속한다.
5. 버전이 같으면: CONTEXT의 `킷 업데이트 마지막 확인`만 오늘로 갱신하고 원래 작업을 잇는다.
6. 버전이 다르면: 사용자에게 "킷 업데이트가 있습니다 (<설치>→<최신>). 적용할까요?"라고 묻고,
   **승인 후에만** 다음을 수행한다. 승인 없이 pull·재설치하지 않는다.
   ```bash
   git -C <킷 경로> pull --ff-only origin master
   <킷 경로>/bootstrap.sh <이 프로젝트 루트>
   <킷 경로>/bootstrap.sh --doctor <이 프로젝트 루트>
   ```
7. 재설치는 킷 소유 파일만 교체한다. tracked `AGENTS.md`/`CLAUDE.md`/소스는 건드리지 않고
   `CONTEXT.md`/`HANDOFF.md`는 보존된다. 사용자가 수정한 킷 소유 파일이 있으면 설치기가
   충돌로 중단하니, 덮어쓰려 하지 말고 그대로 사용자에게 보고한다.
8. 완료 후 CONTEXT의 `킷 업데이트 마지막 확인`과 킷 버전을 갱신하고, 무엇이 바뀌었는지는
   킷의 `docs/change-log/` 최신 항목으로 한 줄 요약해 보고한다.

파일을 프로젝트 간 수동 복사(copy & paste)로 업데이트하지 않는다. manifest 없는 복사본은
guard·doctor·uninstall의 소유권 판정을 깨뜨린다.
