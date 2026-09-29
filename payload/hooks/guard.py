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


def manifest_path(repo: Path) -> Path:
    result = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir", check=True)
    return Path(git_record(result.stdout)) / "agent-project-kit" / "manifest.json"


def manifest(repo: Path) -> dict:
    return json.loads(manifest_path(repo).read_text(encoding="utf-8"))


def kit_managed(repo: Path) -> bool:
    """A repo is kit-managed if it has a kit manifest or hosts this guard copy.

    The guard's own repository stays strict even when its manifest is missing
    or damaged, so tampering with the ledger cannot downgrade its protection.
    Any other repository without a manifest (for example a separate repo that
    the agent commits into with ``git -C``) only gets the generic checks.
    """
    try:
        if manifest_path(repo).exists():
            return True
    except RuntimeError:
        return True
    own = repository(Path(__file__).resolve().parent)
    return own is not None and own == repo


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


def staged_violations(repo: Path, *, managed: bool = True) -> list[str]:
    data: dict | None = None
    if managed:
        try:
            data = manifest(repo)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            return [f"킷 manifest를 검증할 수 없음: {error}"]
    violations: list[str] = []
    for path in staged_paths(repo):
        if data is not None and owned(path, data):
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


GIT_VALUE_OPTIONS = {"-c", "--namespace", "--config-env", "--super-prefix", "--exec-path"}
UNRESOLVED = re.compile(r"[$`]")


def git_subcommand(args: list[str]) -> tuple[str | None, list[str], str | None, str | None]:
    """Split git global options: (subcommand, -C paths, --git-dir, --work-tree)."""
    chdirs: list[str] = []
    git_dir: str | None = None
    work_tree: str | None = None
    index = 0
    while index < len(args):
        item = args[index]
        if item == "-C" and index + 1 < len(args):
            chdirs.append(args[index + 1])
            index += 2
        elif item in {"--git-dir", "--work-tree"} and index + 1 < len(args):
            if item == "--git-dir":
                git_dir = args[index + 1]
            else:
                work_tree = args[index + 1]
            index += 2
        elif item.startswith("--git-dir="):
            git_dir = item.split("=", 1)[1]
            index += 1
        elif item.startswith("--work-tree="):
            work_tree = item.split("=", 1)[1]
            index += 1
        elif item in GIT_VALUE_OPTIONS and index + 1 < len(args):
            index += 2
        elif item.startswith("-"):
            index += 1
        else:
            return item, chdirs, git_dir, work_tree
    return None, chdirs, git_dir, work_tree


def resolve_commit_target(cwd: Path, args: list[str]) -> tuple[Path | None, str | None]:
    """Resolve the repository a ``git [-C ...] commit`` actually writes to."""
    _, chdirs, git_dir, work_tree = git_subcommand(args)
    for value in (*chdirs, git_dir or "", work_tree or ""):
        if UNRESOLVED.search(value):
            return None, f"git 대상 경로를 해석할 수 없음(변수·명령 치환은 지원하지 않음): {value}"
    base = cwd
    for value in chdirs:
        candidate = Path(os.path.expanduser(value))
        base = candidate if candidate.is_absolute() else base / candidate
    if git_dir is None and work_tree is None:
        return repository(base), None
    options = []
    if git_dir is not None:
        options.append(f"--git-dir={os.path.expanduser(git_dir)}")
    if work_tree is not None:
        options.append(f"--work-tree={os.path.expanduser(work_tree)}")
    top = git(base, *options, "rev-parse", "--show-toplevel")
    target_dir = git(base, *options, "rev-parse", "--absolute-git-dir")
    if top.returncode or target_dir.returncode:
        return None, None
    repo = Path(git_record(top.stdout)).resolve()
    discovered = git(repo, "rev-parse", "--absolute-git-dir")
    if discovered.returncode or git_record(discovered.stdout) != git_record(target_dir.stdout):
        return None, "분리된 --git-dir/--work-tree 구성은 검사할 수 없음 — git -C <저장소>로 실행"
    return repo, None


def commit_targets(command: str, cwd: Path) -> list[tuple[Path | None, str | None]]:
    """Every ``git ... commit`` in the command with its resolved target repo."""
    try:
        groups = command_groups(tokenize(command))
    except ValueError:
        if re.search(r"\bgit\b.*\bcommit\b", command, re.S):
            return [(repository(cwd), None)]
        return []
    targets: list[tuple[Path | None, str | None]] = []
    for group in groups:
        for part in group:
            name, args = executable(part)
            if name == "git" and git_subcommand(args)[0] == "commit":
                targets.append(resolve_commit_target(cwd, args))
    return targets


def commit_violations(repo: Path) -> list[str]:
    return staged_violations(repo, managed=kit_managed(repo))


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
        violations = commit_violations(repo)
        return emit_block("agent Stop", violations, agent=True) if violations else 0
    if event == "PreToolUse" and data.get("tool_name") in {"Bash", "shell", "exec_command"}:
        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command") or tool_input.get("cmd") or ""
        reasons = dangerous(command)
        if reasons:
            return emit_block("agent command", reasons, agent=True)
        for target, problem in commit_targets(command, cwd):
            if problem:
                return emit_block("agent commit", [problem], agent=True)
            if target is None:
                return emit_block("agent commit", ["Git worktree를 찾을 수 없음"], agent=True)
            violations = commit_violations(target)
            if violations:
                return emit_block("agent commit", [f"[{target}] {item}" for item in violations], agent=True)
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
