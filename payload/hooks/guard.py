#!/usr/bin/env python3
"""Local safety guard shared by Claude Code, Codex, and Git hooks.

This is a mistake-prevention layer, not a security boundary. Git hooks can be
bypassed and local files remain under the user's control.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


ALLOWED_ENV = {".env.example", ".env.sample", ".env.template"}
SENSITIVE_BASENAMES = {".npmrc", "credentials.json", "secrets.json"}
KEY_PREFIXES = ("id_rsa", "id_ed25519", "id_ecdsa")
CONTENT_PATTERNS = (
    re.compile(rb"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{22,}"),
    re.compile(rb"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(rb"-----BEGIN[ A-Z]*PRIVATE KEY"),
    re.compile(
        rb"(?:api[_-]?key|secret[_-]?key|password|token)"
        rb"\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{16,}",
        re.I,
    ),
)
CONTROL = {"|", "||", "&&", ";", "&"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
DB_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "mongo", "mongosh"}
DROP_STATEMENT = re.compile(r"\bDROP\s+(DATABASE|TABLE|SCHEMA|COLLECTION)\b", re.I)
OID = re.compile(r"^[0-9a-fA-F]{40,64}$")
OWNED_EXACT = {
    "AGENTS.override.md",
    "CLAUDE.local.md",
    ".claude/settings.local.json",
    ".codex/hooks.json",
}
OWNED_PREFIXES = (
    ".agent-project-kit/",
    ".agents/skills/agent-kit-",
    ".claude/skills/agent-kit-",
)


def git(repo: Path, *args: str, check: bool = False, data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", "replace").strip())
    return process


def git_record(output: bytes) -> str:
    value = output.decode("utf-8", "surrogateescape")
    return value[:-1] if value.endswith("\n") else value


def repository(path: Path) -> Path | None:
    process = git(path, "rev-parse", "--show-toplevel")
    if process.returncode:
        return None
    return Path(git_record(process.stdout)).resolve()


def manifest(repo: Path) -> dict:
    result = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir", check=True)
    common = Path(git_record(result.stdout))
    path = common / "agent-project-kit" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def owned(path: str, data: dict) -> bool:
    normalized = path[2:] if path.startswith("./") else path.lstrip("/")
    if normalized in OWNED_EXACT or normalized in set(data.get("owned_paths", [])):
        return True
    prefixes = (*OWNED_PREFIXES, *data.get("owned_prefixes", []))
    return any(normalized.startswith(prefix) for prefix in prefixes)


def sensitive_name(path: str) -> bool:
    candidate = Path(path)
    base = candidate.name
    if base in ALLOWED_ENV:
        return False
    if base.endswith(".pub"):
        return False
    return (
        base == ".env"
        or base.startswith(".env.")
        or base in SENSITIVE_BASENAMES
        or (base.startswith("service-account") and base.endswith(".json"))
        or base.endswith((".p12", ".pem"))
        or base.startswith(KEY_PREFIXES)
        or "secrets" in candidate.parts
    )


def nul_paths(output: bytes) -> list[str]:
    return [
        item.decode("utf-8", "surrogateescape")
        for item in output.split(b"\0")
        if item
    ]


def staged_paths(repo: Path) -> list[str]:
    # Deletions are intentionally allowed so a previously committed local or
    # secret-bearing artifact can be removed from repository history going forward.
    result = git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "-z")
    return nul_paths(result.stdout) if result.returncode == 0 else []


def staged_violations(repo: Path) -> list[str]:
    try:
        data = manifest(repo)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        return [f"킷 manifest를 검증할 수 없음: {error}"]
    violations: list[str] = []
    for path in staged_paths(repo):
        if owned(path, data):
            violations.append(f"로컬 킷 경로 staged: {path}")
            continue
        if sensitive_name(path):
            violations.append(f"민감 파일명 staged: {path}")
            continue
        content = git(repo, "show", f":{path}")
        if content.returncode == 0 and any(pattern.search(content.stdout) for pattern in CONTENT_PATTERNS):
            violations.append(f"secret 의심 내용 staged: {path}")
    return violations


def commit_paths(repo: Path, commit: str) -> list[str]:
    result = git(
        repo,
        "ls-tree",
        "--name-only",
        "-r",
        "-z",
        commit,
    )
    return nul_paths(result.stdout) if result.returncode == 0 else []


def outgoing_commits(repo: Path, push_input: bytes) -> tuple[list[str], list[str]]:
    commits: set[str] = set()
    errors: list[str] = []
    for raw in push_input.splitlines():
        fields = raw.decode("utf-8", "surrogateescape").split()
        if len(fields) != 4:
            errors.append("pre-push 입력 형식을 해석할 수 없음")
            continue
        _, local_oid, _, remote_oid = fields
        if set(local_oid) == {"0"}:
            continue
        if not OID.fullmatch(local_oid) or not OID.fullmatch(remote_oid):
            errors.append("pre-push OID 형식이 올바르지 않음")
            continue
        # A force rewind can make remote_oid..local_oid empty even though the
        # rewound-to tip tree contains a local kit path. Always inspect the
        # exact local tip in addition to any newly introduced ancestry.
        commits.add(local_oid)
        if set(remote_oid) == {"0"}:
            # A new remote ref may expose any ancestor, even one already reachable
            # from a private/other remote; inspect the full pushed ancestry.
            command = ("rev-list", local_oid)
        else:
            command = ("rev-list", f"{remote_oid}..{local_oid}")
        result = git(repo, *command)
        if result.returncode:
            errors.append("outgoing commit 범위를 계산할 수 없음")
            continue
        commits.update(result.stdout.decode("ascii", "replace").splitlines())
    return sorted(commits), errors


def push_violations(repo: Path, push_input: bytes) -> list[str]:
    try:
        data = manifest(repo)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        return [f"킷 manifest를 검증할 수 없음: {error}"]
    commits, violations = outgoing_commits(repo, push_input)
    for commit in commits:
        for path in commit_paths(repo, commit):
            if owned(path, data):
                violations.append(f"outgoing commit {commit[:12]}에 로컬 킷 경로 포함: {path}")
    return violations


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return list(lexer)


def executable(tokens: list[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(tokens):
        name = os.path.basename(tokens[index])
        if name in {"command", "builtin", "nohup"}:
            index += 1
            continue
        if name == "sudo":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
            continue
        if name == "env":
            index += 1
            while index < len(tokens) and ("=" in tokens[index] or tokens[index].startswith("-")):
                index += 1
            continue
        return name, tokens[index + 1 :]
    return "", []


def command_groups(tokens: list[str]) -> list[list[list[str]]]:
    groups: list[list[list[str]]] = []
    pipeline: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in CONTROL:
            if current:
                pipeline.append(current)
                current = []
            if token != "|" and pipeline:
                groups.append(pipeline)
                pipeline = []
        else:
            current.append(token)
    if current:
        pipeline.append(current)
    if pipeline:
        groups.append(pipeline)
    return groups


def recursive_force(args: list[str]) -> bool:
    letters: set[str] = set()
    long_flags: set[str] = set()
    for value in args:
        if re.fullmatch(r"-[A-Za-z]+", value):
            letters.update(value[1:])
        elif value in {"--recursive", "--force"}:
            long_flags.add(value)
    return (bool({"r", "R"} & letters) or "--recursive" in long_flags) and (
        "f" in letters or "--force" in long_flags
    )


def dangerous(command: str, depth: int = 0) -> list[str]:
    if depth > 2:
        return []
    try:
        tokens = tokenize(command)
    except ValueError:
        return ["명령을 안전하게 파싱할 수 없음"] if "git commit" in command else []
    reasons: list[str] = []
    for pipeline in command_groups(tokens):
        commands = [executable(part) for part in pipeline]
        text = " ".join(token for part in pipeline for token in part)
        for name, args in commands:
            if name == "rm" and recursive_force(args):
                reasons.append("재귀+강제 삭제")
            if name == "git" and "push" in args:
                push_args = args[args.index("push") + 1 :]
                if any(
                    item in {"-f", "--force", "--mirror"}
                    or (item.startswith("-") and not item.startswith("--") and "f" in item[1:])
                    or item.startswith("--force=")
                    or item.startswith("--force-with-lease")
                    or (item.startswith("+") and len(item) > 1)
                    for item in push_args
                ):
                    reasons.append("force/history-rewrite push")
            if name == "chmod" and "777" in args:
                reasons.append("chmod 777")
            if name in DB_CLIENTS and DROP_STATEMENT.search(text):
                reasons.append("DB DROP")
            if name in SHELLS and "-c" in args:
                index = args.index("-c")
                if index + 1 < len(args):
                    reasons.extend(dangerous(args[index + 1], depth + 1))
        names = {name for name, _ in commands}
        if names & {"curl", "wget"} and names & SHELLS:
            reasons.append("원격 스크립트 직접 실행")
    return sorted(set(reasons))


def mentions_git_commit(command: str) -> bool:
    try:
        for group in command_groups(tokenize(command)):
            for part in group:
                name, args = executable(part)
                if name == "git" and "commit" in args:
                    return True
    except ValueError:
        return bool(re.search(r"\bgit\b.*\bcommit\b", command, re.S))
    return False


def emit_block(context: str, violations: list[str], agent: bool = False) -> int:
    print(f"차단됨 ({context}):", file=sys.stderr)
    for item in violations:
        print(f"  - {item}", file=sys.stderr)
    print("경로를 stage에서 제거하고 비밀은 즉시 폐기·회전하세요.", file=sys.stderr)
    return 2 if agent else 1


def git_pre_commit() -> int:
    repo = repository(Path.cwd())
    if repo is None:
        return emit_block("pre-commit", ["Git worktree를 찾을 수 없음"])
    violations = staged_violations(repo)
    return emit_block("pre-commit", violations) if violations else 0


def git_pre_push() -> int:
    repo = repository(Path.cwd())
    if repo is None:
        return emit_block("pre-push", ["Git worktree를 찾을 수 없음"])
    violations = push_violations(repo, sys.stdin.buffer.read())
    return emit_block("pre-push", violations) if violations else 0


def agent_hook() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    event = data.get("hook_event_name") or data.get("event")
    cwd = Path(data.get("cwd") or os.getcwd())
    repo = repository(cwd)
    if event == "Stop":
        if data.get("stop_hook_active") or repo is None:
            return 0
        violations = staged_violations(repo)
        return emit_block("agent Stop", violations, agent=True) if violations else 0
    if event == "PreToolUse" and data.get("tool_name") in {"Bash", "shell", "exec_command"}:
        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command") or tool_input.get("cmd") or ""
        reasons = dangerous(command)
        if reasons:
            return emit_block("agent command", reasons, agent=True)
        if mentions_git_commit(command):
            if repo is None:
                return emit_block("agent commit", ["Git worktree를 찾을 수 없음"], agent=True)
            violations = staged_violations(repo)
            if violations:
                return emit_block("agent commit", violations, agent=True)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: guard.py git-pre-commit|git-pre-push|agent-hook", file=sys.stderr)
        return 2
    if sys.argv[1] == "git-pre-commit":
        return git_pre_commit()
    if sys.argv[1] == "git-pre-push":
        return git_pre_push()
    if sys.argv[1] == "agent-hook":
        return agent_hook()
    print(f"unknown mode: {sys.argv[1]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
