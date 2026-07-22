#!/usr/bin/env python3
"""PreToolUse(Bash) — 되돌릴 수 없는 파괴적 명령을 차단한다.

settings.json의 권한 deny(패턴 매칭)가 놓치는 어순·플래그 변형을 정규식/토큰
분석으로 보완하는 2차 방어선. exit 2 = 차단(stderr가 Claude에게 전달됨).
정말 필요한 명령이면 사용자가 터미널에서 직접 실행한다.
"""

import json
import re
import sys

SEGMENT_SPLIT = re.compile(r"[|;&]+")
SHORT_FLAG = re.compile(r"^-[a-zA-Z]+$")


def rm_recursive_force(segment):
    """rm에 재귀(r/R/--recursive)와 강제(f/--force)가 함께 있으면 True.
    결합(-rf)·분리(-r -f)·순서 무관 모두 잡는다."""
    tokens = segment.split()
    if "rm" not in tokens:
        return False
    letters = set()
    longs = set()
    for tok in tokens[tokens.index("rm") + 1 :]:
        if SHORT_FLAG.match(tok):
            letters.update(tok[1:])
        elif tok in ("--recursive", "--force"):
            longs.add(tok)
    recursive = bool({"r", "R"} & letters) or "--recursive" in longs
    force = "f" in letters or "--force" in longs
    return recursive and force


REGEX_RULES = [
    (
        re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", re.I),
        "원격 스크립트를 셸에 직접 파이프(curl | sh)",
    ),
    (
        re.compile(r"\bgit\s+push\b[^|;&]*\s(--force(-with-lease)?\b|-f\b)"),
        "force push(원격 이력 파괴)",
    ),
    (re.compile(r"\bchmod\b[^|;&]*\b777\b"), "chmod 777"),
]

DB_CLIENT = re.compile(r"\b(psql|mysql|mariadb|sqlite3|mongosh?)\b")
DROP_STMT = re.compile(r"\bDROP\s+(DATABASE|TABLE|SCHEMA|COLLECTION)\b", re.I)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd:
        sys.exit(0)

    reasons = []
    for seg in SEGMENT_SPLIT.split(cmd):
        if rm_recursive_force(seg):
            reasons.append("재귀+강제 삭제(rm -rf 계열)")
        if DB_CLIENT.search(seg) and DROP_STMT.search(seg):
            reasons.append("DB 클라이언트로 DROP 실행")
    for rx, label in REGEX_RULES:
        if rx.search(cmd):
            reasons.append(label)

    if reasons:
        sys.stderr.write(
            "차단됨(안전 훅): "
            + ", ".join(sorted(set(reasons)))
            + ". 정말 필요하면 사용자가 터미널에서 직접 실행할 것.\n"
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
