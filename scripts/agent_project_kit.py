#!/usr/bin/env python3
"""Install agent-project-kit as repository-local, untracked harness state.

The target worktree receives only explicitly allowlisted local adapters. Git's
common directory owns the installation manifest and hook dispatcher so linked
worktrees are supported and uninstall can restore the previous hook setting.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable


KIT_NAME = "agent-project-kit"
KIT_VERSION = "1.4.1"
BLOCK_START = "# >>> agent-project-kit managed (local-only; do not edit)"
BLOCK_END = "# <<< agent-project-kit managed"
HOOK_CONFIG_START = "# >>> agent-project-kit core.hooksPath (managed; do not edit)"
HOOK_CONFIG_END = "# <<< agent-project-kit core.hooksPath managed"
HOOK_NAMES = (
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
    "pre-commit",
    "pre-merge-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-push",
    "pre-auto-gc",
    "post-rewrite",
    "post-index-change",
    "reference-transaction",
    "sendemail-validate",
    "fsmonitor-watchman",
    "p4-changelist",
    "p4-prepare-changelist",
    "p4-post-changelist",
    "p4-pre-submit",
    "pre-receive",
    "update",
    "proc-receive",
    "post-receive",
    "post-update",
    "push-to-checkout",
)
# Owned-path schema history. Every shipped schema version is frozen here so a
# manifest written by an older kit can still be validated, upgraded in place,
# and uninstalled without trusting the manifest's own allowlists.
SCHEMA_VERSION = 5
SCHEMA_SKILLS: dict[int, tuple[str, ...]] = {
    1: ("init", "adopt", "handoff", "wrap-up"),
    2: ("init", "adopt", "handoff", "wrap-up", "skill-sync"),
    3: ("init", "adopt", "handoff", "wrap-up", "skill-sync"),
    4: ("init", "adopt", "handoff", "wrap-up", "skill-sync", "update"),
    5: ("init", "adopt", "handoff", "wrap-up", "skill-sync", "update", "jira-ticket"),
}
SCHEMA_TEMPLATES: dict[int, tuple[str, ...]] = {
    1: (),
    2: ("AGENTS.template.md", "CLAUDE.template.md"),
    3: ("AGENTS.template.md", "CLAUDE.template.md"),
    4: ("AGENTS.template.md", "CLAUDE.template.md"),
    5: ("AGENTS.template.md", "CLAUDE.template.md"),
}
SCHEMA_AGENTS: dict[int, tuple[str, ...]] = {
    1: (),
    2: (),
    3: ("developer", "review-killer"),
    4: ("developer", "review-killer"),
    5: ("developer", "review-killer"),
}
# Mutable per-machine config seeds deployed under .agent-project-kit/. They are
# owned (preflight-safe) but user-editable and preserved across reinstalls.
SCHEMA_CONFIGS: dict[int, tuple[str, ...]] = {
    1: (),
    2: (),
    3: (),
    4: (),
    5: ("jira-ticket.config.json",),
}
CODEX_AGENT_MODEL = "gpt-5.6-sol"
CODEX_AGENT_REASONING = "high"
LOCK_FILE = "agent-project-kit.lock"
LOCK_MAGIC = b"agent-project-kit common-dir lock v1\n"
MIN_GIT_VERSION = (2, 31)


def resolve_schema_version(version: int | None) -> int:
    resolved = SCHEMA_VERSION if version is None else version
    if resolved not in SCHEMA_SKILLS:
        raise RuntimeError(f"지원하지 않는 manifest schema version입니다: {resolved}")
    return resolved


def mutable_paths(version: int | None = None) -> set[str]:
    version = resolve_schema_version(version)
    paths = {
        ".agent-project-kit/CONTEXT.md",
        ".agent-project-kit/HANDOFF.md",
    }
    paths.update(f".agent-project-kit/{name}" for name in SCHEMA_CONFIGS[version])
    return paths


def payload_map(version: int | None = None) -> dict[str, str]:
    version = resolve_schema_version(version)
    mapping = {
        "runtime/AGENTS.override.md": "AGENTS.override.md",
        "runtime/CLAUDE.local.md": "CLAUDE.local.md",
        "runtime/CONTEXT.md": ".agent-project-kit/CONTEXT.md",
        "runtime/HANDOFF.md": ".agent-project-kit/HANDOFF.md",
        "runtime/claude-settings.local.json": ".claude/settings.local.json",
        "runtime/codex-hooks.json": ".codex/hooks.json",
        "hooks/guard.py": ".agent-project-kit/hooks/guard.py",
    }
    for name in SCHEMA_TEMPLATES[version]:
        mapping[f"templates/{name}"] = f".agent-project-kit/templates/{name}"
    for name in SCHEMA_CONFIGS[version]:
        mapping[f"runtime/{name}"] = f".agent-project-kit/{name}"
    for skill in SCHEMA_SKILLS[version]:
        source = f"skills/agent-kit-{skill}/SKILL.md"
        mapping[f"{source}::agents"] = f".agents/skills/agent-kit-{skill}/SKILL.md"
        mapping[f"{source}::claude"] = f".claude/skills/agent-kit-{skill}/SKILL.md"
    if SCHEMA_AGENTS[version]:
        mapping["runtime/AGENT-RULES.md"] = ".agent-project-kit/AGENT-RULES.md"
    for agent in SCHEMA_AGENTS[version]:
        source = f"agents/{agent}/AGENT.md"
        mapping[f"{source}::claude"] = f".claude/agents/{agent}.md"
        mapping[f"{source}::codex"] = f".codex/agents/{agent}.toml"
    return mapping


def parse_agent_frontmatter(data: bytes) -> tuple[dict[str, str], str]:
    """Split an AGENT.md payload into frontmatter fields and markdown body."""
    text = data.decode("utf-8")
    if not text.startswith("---\n"):
        raise RuntimeError("AGENT.md payload에 frontmatter가 없습니다.")
    try:
        header, body = text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise RuntimeError("AGENT.md frontmatter 경계를 해석할 수 없습니다.") from error
    fields: dict[str, str] = {}
    for line in header.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    for required in ("name", "description"):
        if not fields.get(required):
            raise RuntimeError(f"AGENT.md frontmatter에 {required}가 없습니다.")
    return fields, body.lstrip("\n")


def toml_basic_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def codex_agent_toml(data: bytes) -> bytes:
    """Render a Claude-format AGENT.md payload as a Codex .codex/agents TOML."""
    fields, body = parse_agent_frontmatter(data)
    lines = [
        "# generated by agent-project-kit from the shared AGENT.md payload; do not edit",
        f"name = {toml_basic_string(fields['name'])}",
        f"description = {toml_basic_string(fields['description'])}",
        f"model = {toml_basic_string(CODEX_AGENT_MODEL)}",
        f"model_reasoning_effort = {toml_basic_string(CODEX_AGENT_REASONING)}",
        'sandbox_mode = "workspace-write"',
        f"developer_instructions = {toml_basic_string(body)}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_worktree_file(key: str, data: bytes) -> bytes:
    """Payload bytes are copied verbatim except Codex agent TOML rendering."""
    if key.endswith("::codex") and source_rel(key).startswith("agents/"):
        return codex_agent_toml(data)
    return data


def source_rel(key: str) -> str:
    return key.split("::", 1)[0]


def expected_payload_files() -> set[str]:
    return {source_rel(key) for key in payload_map()}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(
    root: Path, *args: str, check: bool = True, input_data: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode != 0:
        detail = process.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} 실패: {detail or '원인 미상'}")
    return process


def installed_git_version() -> tuple[int, int]:
    process = subprocess.run(
        ["git", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    text = process.stdout.decode("utf-8", "replace")
    match = re.search(r"\bgit version (\d+)\.(\d+)", text)
    if process.returncode != 0 or not match:
        raise RuntimeError("Git 버전을 확인할 수 없습니다.")
    return (int(match.group(1)), int(match.group(2)))


def ensure_git_version() -> None:
    current = installed_git_version()
    if current < MIN_GIT_VERSION:
        required = ".".join(str(item) for item in MIN_GIT_VERSION)
        found = ".".join(str(item) for item in current)
        raise RuntimeError(f"Git {required}+가 필요합니다. 현재: {found}")


def git_text(root: Path, *args: str) -> str:
    value = run_git(root, *args).stdout.decode("utf-8", "surrogateescape")
    return value[:-1] if value.endswith("\n") else value


def find_repository(requested: str) -> tuple[Path, Path]:
    candidate = Path(requested).expanduser()
    if not candidate.is_dir():
        raise RuntimeError(f"대상 디렉터리가 없습니다: {requested}")
    candidate = candidate.resolve()
    probe = run_git(candidate, "rev-parse", "--is-inside-work-tree", check=False)
    if probe.returncode != 0 or probe.stdout.strip() != b"true":
        raise RuntimeError(
            "agent-project-kit은 Git worktree에서만 설치할 수 있습니다 (먼저 git init)."
        )
    root = Path(git_text(candidate, "rev-parse", "--show-toplevel")).resolve()
    common = Path(
        git_text(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    return root, common


@contextmanager
def common_directory_lock(common: Path, *, create: bool) -> Iterable[None]:
    """Serialize lifecycle operations that share hooks and an installation manifest."""
    lock_path = common / LOCK_FILE
    if not create and not lock_path.exists():
        yield
        return
    base_flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    created = False
    try:
        if create:
            try:
                descriptor = os.open(
                    lock_path,
                    base_flags | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                created = True
            except FileExistsError:
                descriptor = os.open(lock_path, base_flags)
        else:
            descriptor = os.open(lock_path, base_flags)
    except OSError as error:
        raise RuntimeError(
            f"킷 lock을 안전하게 열 수 없습니다: {lock_path}: {error}"
        ) from error
    try:
        with os.fdopen(descriptor, "r+b", closefd=True) as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise RuntimeError(
                    f"킷 lock 경로가 regular file이 아닙니다: {lock_path}"
                )
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX if create else fcntl.LOCK_SH)
            stream.seek(0)
            content = stream.read()
            if content and content != LOCK_MAGIC:
                raise RuntimeError(
                    f"킷 lock 경로가 기존 파일과 충돌합니다: {lock_path}"
                )
            if not content and created:
                stream.seek(0)
                stream.write(LOCK_MAGIC)
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o600)
            elif not content:
                raise RuntimeError(f"킷 lock 파일이 비어 있습니다: {lock_path}")
            yield
    except BaseException:
        # fdopen owns and closes descriptor after entry; close only if entry itself failed.
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def ensure_relative(rel: str) -> None:
    path = Path(rel)
    if path.is_absolute() or not rel or ".." in path.parts:
        raise RuntimeError(f"안전하지 않은 소유 경로: {rel}")


def reject_symlink_escape(root: Path, rel: str) -> None:
    ensure_relative(rel)
    current = root
    for part in Path(rel).parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"심볼릭 링크 경로에는 설치하지 않습니다: {current}")


def file_matches_state(path: Path, state: tuple[bool, bytes, int]) -> bool:
    existed, content, mode = state
    try:
        if not existed:
            return not path.exists() and not path.is_symlink()
        return (
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == content
            and stat.S_IMODE(path.stat().st_mode) == mode
        )
    except OSError:
        return False


def capture_file_state(path: Path) -> tuple[bool, bytes, int]:
    if path.is_symlink():
        raise RuntimeError(
            f"심볼릭 링크 파일은 소유권 snapshot으로 사용하지 않습니다: {path}"
        )
    if not path.exists():
        return (False, b"", 0o644)
    if not path.is_file():
        raise RuntimeError(f"regular file이 아닌 경로는 수정하지 않습니다: {path}")
    return (True, path.read_bytes(), stat.S_IMODE(path.stat().st_mode))


def atomic_write(
    path: Path,
    data: bytes,
    mode: int = 0o644,
    *,
    expected: tuple[bool, bytes, int] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if expected is not None and not file_matches_state(path, expected):
            raise RuntimeError(f"동시 변경을 감지해 파일을 덮어쓰지 않습니다: {path}")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def unlink_if_unchanged(path: Path, expected: tuple[bool, bytes, int]) -> None:
    if not expected[0]:
        return
    if not file_matches_state(path, expected):
        raise RuntimeError(f"동시 변경을 감지해 파일을 삭제하지 않습니다: {path}")
    path.unlink()


def git_config_lock_path(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


def atomic_write_git_config(
    path: Path,
    data: bytes,
    mode: int,
    *,
    expected: tuple[bool, bytes, int],
) -> None:
    """Replace a Git config while holding the lock used by ``git config``."""
    lock_path = git_config_lock_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise RuntimeError(
            f"Git config lock을 획득할 수 없어 변경하지 않습니다: {lock_path}: {error}"
        ) from error
    replaced = False
    try:
        if not file_matches_state(path, expected):
            raise RuntimeError(
                f"동시 변경을 감지해 Git config를 덮어쓰지 않습니다: {path}"
            )
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        if not file_matches_state(path, expected):
            raise RuntimeError(
                f"동시 변경을 감지해 Git config를 덮어쓰지 않습니다: {path}"
            )
        os.replace(lock_path, path)
        replaced = True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not replaced:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def unlink_git_config(path: Path, expected: tuple[bool, bytes, int]) -> None:
    if not expected[0]:
        return
    lock_path = git_config_lock_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise RuntimeError(
            f"Git config lock을 획득할 수 없어 삭제하지 않습니다: {lock_path}: {error}"
        ) from error
    try:
        if not file_matches_state(path, expected):
            raise RuntimeError(
                f"동시 변경을 감지해 Git config를 삭제하지 않습니다: {path}"
            )
        path.unlink()
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_recorded(
    path: Path,
    data: bytes,
    mode: int,
    expected: tuple[bool, bytes, int],
    journal: dict[Path, tuple[bool, bytes, int]],
) -> None:
    journal[path] = (True, data, mode)
    try:
        atomic_write(path, data, mode, expected=expected)
    except BaseException:
        if file_matches_state(path, expected):
            journal.pop(path, None)
        raise


def unlink_recorded(
    path: Path,
    expected: tuple[bool, bytes, int],
    journal: dict[Path, tuple[bool, bytes, int]],
) -> None:
    if not expected[0]:
        return
    journal[path] = (False, b"", 0o644)
    try:
        unlink_if_unchanged(path, expected)
    except BaseException:
        if file_matches_state(path, expected):
            journal.pop(path, None)
        raise


def atomic_write_git_config_recorded(
    path: Path,
    data: bytes,
    mode: int,
    expected: tuple[bool, bytes, int],
    journal: dict[Path, tuple[bool, bytes, int]],
) -> None:
    journal[path] = (True, data, mode)
    try:
        atomic_write_git_config(path, data, mode, expected=expected)
    except BaseException:
        if file_matches_state(path, expected):
            journal.pop(path, None)
        raise


def unlink_git_config_recorded(
    path: Path,
    expected: tuple[bool, bytes, int],
    journal: dict[Path, tuple[bool, bytes, int]],
) -> None:
    if not expected[0]:
        return
    journal[path] = (False, b"", 0o644)
    try:
        unlink_git_config(path, expected)
    except BaseException:
        if file_matches_state(path, expected):
            journal.pop(path, None)
        raise


def read_manifest_state(
    path: Path,
    state: tuple[bool, bytes, int],
    required: bool = False,
) -> dict | None:
    if not state[0]:
        if required:
            raise RuntimeError(
                "설치 manifest가 없습니다. 먼저 install/adopt를 실행하세요."
            )
        return None
    if path.parent.is_symlink():
        raise RuntimeError(f"manifest가 심볼릭 링크입니다: {path}")
    try:
        value = json.loads(state[1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"manifest를 읽을 수 없습니다: {error}") from error
    validate_manifest(value, path)
    return value


def read_manifest(path: Path, required: bool = False) -> dict | None:
    return read_manifest_state(path, capture_file_state(path), required)


def common_owned_paths() -> list[str]:
    return sorted(
        {
            "dispatcher.py",
            "guard.py",
            *(f"hooks/{name}" for name in HOOK_NAMES),
        }
    )


def validate_hash_map(name: str, value: object, expected_paths: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected_paths:
        raise RuntimeError(f"manifest {name} allowlist가 현재 schema와 다릅니다.")
    for rel, digest in value.items():
        if not isinstance(rel, str):
            raise RuntimeError(f"manifest {name} 경로 형식이 잘못되었습니다.")
        ensure_relative(rel)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RuntimeError(f"manifest {name} hash 형식이 잘못되었습니다: {rel}")


def validate_manifest(value: object, path: Path) -> None:
    """Treat the local manifest as untrusted input before reading or removing paths."""
    expected_keys = {
        "schema_version",
        "kit",
        "kit_version",
        "install_mode",
        "worktree_root",
        "git_common_dir",
        "owned_paths",
        "owned_prefixes",
        "mutable_paths",
        "mutable_files",
        "worktree_files",
        "common_files",
        "exclude_lines",
        "exclude",
        "git",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise RuntimeError("지원하지 않거나 손상된 manifest 형식입니다.")
    if value.get("schema_version") not in SCHEMA_SKILLS or value.get("kit") != KIT_NAME:
        raise RuntimeError("지원하지 않는 manifest schema 또는 kit입니다.")
    manifest_version = value["schema_version"]
    if not isinstance(value.get("kit_version"), str) or not value["kit_version"]:
        raise RuntimeError("manifest kit_version 형식이 잘못되었습니다.")
    if value.get("install_mode") not in {"install", "adopt"}:
        raise RuntimeError("manifest install_mode 형식이 잘못되었습니다.")
    for field in ("worktree_root", "git_common_dir"):
        raw = value.get(field)
        if (
            not isinstance(raw, str)
            or not raw
            or "\x00" in raw
            or not Path(raw).is_absolute()
        ):
            raise RuntimeError(f"manifest {field} 형식이 잘못되었습니다.")
    if value["git_common_dir"] != str(path.parent.parent):
        raise RuntimeError("manifest git_common_dir가 실제 위치와 다릅니다.")

    expected_owned = owned_paths(manifest_version)
    expected_mutable = sorted(mutable_paths(manifest_version))
    expected_immutable = set(expected_owned) - mutable_paths(manifest_version)
    if value.get("owned_paths") != expected_owned:
        raise RuntimeError("manifest owned_paths allowlist가 기록된 schema와 다릅니다.")
    if value.get("owned_prefixes") != owned_prefixes():
        raise RuntimeError(
            "manifest owned_prefixes allowlist가 기록된 schema와 다릅니다."
        )
    if value.get("mutable_paths") != expected_mutable:
        raise RuntimeError(
            "manifest mutable_paths allowlist가 기록된 schema와 다릅니다."
        )
    if value.get("exclude_lines") != exclude_lines(manifest_version):
        raise RuntimeError(
            "manifest exclude_lines allowlist가 기록된 schema와 다릅니다."
        )
    exclude = value.get("exclude")
    expected_exclude_keys = {
        "original_existed",
        "original_mode",
        "original_size",
        "original_sha256",
        "installed_mode",
        "installed_sha256",
    }
    if not isinstance(exclude, dict) or set(exclude) != expected_exclude_keys:
        raise RuntimeError("manifest exclude 복원 정보 형식이 잘못되었습니다.")
    if not isinstance(exclude.get("original_existed"), bool):
        raise RuntimeError("manifest exclude original_existed 형식이 잘못되었습니다.")
    for field in ("original_mode", "installed_mode", "original_size"):
        item = exclude.get(field)
        if (
            not isinstance(item, int)
            or isinstance(item, bool)
            or item < 0
            or (field.endswith("mode") and item > 0o7777)
        ):
            raise RuntimeError(f"manifest exclude {field} 형식이 잘못되었습니다.")
    for field in ("original_sha256", "installed_sha256"):
        digest = exclude.get(field)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RuntimeError(f"manifest exclude {field} 형식이 잘못되었습니다.")
    if exclude["installed_mode"] != exclude["original_mode"]:
        raise RuntimeError("manifest exclude mode 복원 정보가 일관되지 않습니다.")
    if not exclude["original_existed"] and (
        exclude["original_size"] != 0 or exclude["original_sha256"] != sha256_bytes(b"")
    ):
        raise RuntimeError("manifest exclude 비존재 원본 정보가 일관되지 않습니다.")
    validate_hash_map(
        "mutable_files", value.get("mutable_files"), set(expected_mutable)
    )
    validate_hash_map("worktree_files", value.get("worktree_files"), expected_immutable)
    validate_hash_map(
        "common_files", value.get("common_files"), set(common_owned_paths())
    )

    git = value.get("git")
    expected_git_keys = {
        "previous_local_hooks_paths",
        "previous_worktree_hooks_paths",
        "previous_effective_hooks_dir",
        "previous_hooks_path_raw",
        "installed_hooks_scope",
        "installed_hooks_path",
        "installed_config",
    }
    if not isinstance(git, dict) or set(git) != expected_git_keys:
        raise RuntimeError("manifest git 복원 정보 형식이 잘못되었습니다.")
    previous_values = git.get("previous_local_hooks_paths")
    if not isinstance(previous_values, list) or not all(
        isinstance(item, str) and "\x00" not in item for item in previous_values
    ):
        raise RuntimeError("manifest previous_local_hooks_paths 형식이 잘못되었습니다.")
    previous_worktree_values = git.get("previous_worktree_hooks_paths")
    if not isinstance(previous_worktree_values, list) or not all(
        isinstance(item, str) and "\x00" not in item
        for item in previous_worktree_values
    ):
        raise RuntimeError(
            "manifest previous_worktree_hooks_paths 형식이 잘못되었습니다."
        )
    previous_dir = git.get("previous_effective_hooks_dir")
    if (
        not isinstance(previous_dir, str)
        or not previous_dir
        or "\x00" in previous_dir
        or not Path(previous_dir).is_absolute()
    ):
        raise RuntimeError(
            "manifest previous_effective_hooks_dir 형식이 잘못되었습니다."
        )
    if git.get("installed_hooks_path") != str(path.parent / "hooks"):
        raise RuntimeError("manifest installed_hooks_path가 실제 위치와 다릅니다.")
    if git.get("installed_hooks_scope") not in {"local", "worktree"}:
        raise RuntimeError("manifest installed_hooks_scope 형식이 잘못되었습니다.")
    previous_raw = git.get("previous_hooks_path_raw")
    if previous_raw is not None and (
        not isinstance(previous_raw, str) or not previous_raw or "\x00" in previous_raw
    ):
        raise RuntimeError("manifest previous_hooks_path_raw 형식이 잘못되었습니다.")
    installed_config = git.get("installed_config")
    expected_config_keys = {
        "path",
        "original_existed",
        "original_mode",
        "original_size",
        "original_sha256",
        "installed_mode",
        "installed_sha256",
    }
    if (
        not isinstance(installed_config, dict)
        or set(installed_config) != expected_config_keys
    ):
        raise RuntimeError("manifest installed_config 복원 정보 형식이 잘못되었습니다.")
    config_path = installed_config.get("path")
    if (
        not isinstance(config_path, str)
        or not config_path
        or "\x00" in config_path
        or not Path(config_path).is_absolute()
    ):
        raise RuntimeError("manifest installed_config path 형식이 잘못되었습니다.")
    if not isinstance(installed_config.get("original_existed"), bool):
        raise RuntimeError(
            "manifest installed_config original_existed 형식이 잘못되었습니다."
        )
    for field in ("original_mode", "installed_mode", "original_size"):
        item = installed_config.get(field)
        if (
            not isinstance(item, int)
            or isinstance(item, bool)
            or item < 0
            or (field.endswith("mode") and item > 0o7777)
        ):
            raise RuntimeError(
                f"manifest installed_config {field} 형식이 잘못되었습니다."
            )
    for field in ("original_sha256", "installed_sha256"):
        digest = installed_config.get(field)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RuntimeError(
                f"manifest installed_config {field} 형식이 잘못되었습니다."
            )
    if installed_config["installed_mode"] != installed_config["original_mode"]:
        raise RuntimeError(
            "manifest installed_config mode 복원 정보가 일관되지 않습니다."
        )
    if not installed_config["original_existed"] and (
        installed_config["original_size"] != 0
        or installed_config["original_sha256"] != sha256_bytes(b"")
    ):
        raise RuntimeError(
            "manifest installed_config 비존재 원본 정보가 일관되지 않습니다."
        )


def load_payload(payload: Path) -> dict[str, bytes]:
    expected = expected_payload_files()
    actual = {
        item.relative_to(payload).as_posix()
        for item in payload.rglob("*")
        if item.is_file()
        and item.name != ".DS_Store"
        and "__pycache__" not in item.parts
    }
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append("누락=" + ", ".join(missing))
        if unexpected:
            details.append("allowlist 밖=" + ", ".join(unexpected))
        raise RuntimeError("payload allowlist 불일치: " + "; ".join(details))
    return {rel: (payload / rel).read_bytes() for rel in sorted(expected)}


def owned_paths(version: int | None = None) -> list[str]:
    return sorted(set(payload_map(version).values()))


def owned_prefixes() -> list[str]:
    return [
        ".agent-project-kit/",
        ".agents/skills/agent-kit-",
        ".claude/skills/agent-kit-",
    ]


def expected_worktree_mode(rel: str) -> int:
    return 0o755 if rel == ".agent-project-kit/hooks/guard.py" else 0o644


def expected_common_mode(rel: str) -> int:
    del rel
    return 0o755


def exclude_lines(version: int | None = None) -> list[str]:
    version = resolve_schema_version(version)
    lines = ["/.agent-project-kit/", "/AGENTS.override.md", "/CLAUDE.local.md"]
    lines.extend(
        [
            "/.claude/settings.local.json",
            "/.codex/hooks.json",
        ]
    )
    for skill in SCHEMA_SKILLS[version]:
        lines.append(f"/.agents/skills/agent-kit-{skill}/")
        lines.append(f"/.claude/skills/agent-kit-{skill}/")
    for agent in SCHEMA_AGENTS[version]:
        lines.append(f"/.claude/agents/{agent}.md")
        lines.append(f"/.codex/agents/{agent}.toml")
    return lines


def expected_exclude_block(version: int | None = None) -> str:
    return "\n".join([BLOCK_START, *exclude_lines(version), BLOCK_END])


def append_managed_block(original: bytes, version: int | None = None) -> bytes:
    start = BLOCK_START.encode("utf-8")
    end = BLOCK_END.encode("utf-8")
    if start in original or end in original:
        raise RuntimeError(
            "info/exclude에 기존 managed marker가 있어 자동 수정하지 않습니다."
        )
    separator = b"" if not original or original.endswith(b"\n") else b"\n"
    return (
        original + separator + expected_exclude_block(version).encode("utf-8") + b"\n"
    )


def tracked_owned(root: Path) -> list[str]:
    result = run_git(root, "ls-files", "-z")
    paths = [
        item.decode("utf-8", "surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]
    exact = set(owned_paths())
    return [
        path
        for path in paths
        if path in exact or any(path.startswith(prefix) for prefix in owned_prefixes())
    ]


def is_runtime_byproduct(rel: str) -> bool:
    """Benign runtime droppings under kit-reserved prefixes.

    These are produced by normal operation (python bytecode cache, Finder
    metadata, the kit's own crash-leftover ``<file>.lock`` convention). They
    must not block reinstall/uninstall preflight, and uninstall removes them —
    otherwise they surface in git status once the managed exclude is restored.
    """
    parts = Path(rel).parts
    name = parts[-1] if parts else ""
    return "__pycache__" in parts or name == ".DS_Store" or name.endswith(".lock")


def runtime_byproduct_files(root: Path, common_root: Path) -> list[Path]:
    """Kit-caused byproduct files inside kit-reserved locations only."""
    scan_roots: list[Path] = []
    local_root = root / ".agent-project-kit"
    if local_root.is_dir() and not local_root.is_symlink():
        scan_roots.append(local_root)
    for provider in (".agents", ".claude"):
        skills_root = root / provider / "skills"
        if skills_root.is_dir() and not skills_root.is_symlink():
            scan_roots.extend(
                child
                for child in skills_root.iterdir()
                if child.name.startswith("agent-kit-")
                and child.is_dir()
                and not child.is_symlink()
            )
    if common_root.is_dir() and not common_root.is_symlink():
        scan_roots.append(common_root)
    found: list[Path] = []
    for base in scan_roots:
        for item in base.rglob("*"):
            if (
                item.is_file()
                and not item.is_symlink()
                and is_runtime_byproduct(item.relative_to(base).as_posix())
            ):
                found.append(item)
    return sorted(set(found))


def reserved_collisions(root: Path, old: dict | None) -> list[str]:
    """Find files under kit-reserved prefixes that the manifest does not own."""
    allowed = set((old or {}).get("owned_paths", []))
    candidates: list[Path] = []
    local_root = root / ".agent-project-kit"
    if local_root.exists() or local_root.is_symlink():
        if local_root.is_dir() and not local_root.is_symlink():
            candidates.extend(
                item
                for item in local_root.rglob("*")
                if not item.is_dir() or item.is_symlink()
            )
        else:
            candidates.append(local_root)
    for provider in (".agents", ".claude"):
        skills_root = root / provider / "skills"
        if skills_root.is_dir() and not skills_root.is_symlink():
            for child in skills_root.iterdir():
                if not child.name.startswith("agent-kit-"):
                    continue
                if child.is_dir() and not child.is_symlink():
                    candidates.extend(
                        item
                        for item in child.rglob("*")
                        if not item.is_dir() or item.is_symlink()
                    )
                else:
                    candidates.append(child)
    return sorted(
        {
            path.relative_to(root).as_posix()
            for path in candidates
            if path.relative_to(root).as_posix() not in allowed
            and not is_runtime_byproduct(path.relative_to(root).as_posix())
        }
    )


def common_reserved_collisions(common_root: Path, old: dict | None) -> list[str]:
    if not common_root.exists() or common_root.is_symlink():
        return []
    allowed = set((old or {}).get("common_files", {}))
    if old:
        allowed.add("manifest.json")
    return sorted(
        {
            item.relative_to(common_root).as_posix()
            for item in common_root.rglob("*")
            if (not item.is_dir() or item.is_symlink())
            and item.relative_to(common_root).as_posix() not in allowed
            and not is_runtime_byproduct(item.relative_to(common_root).as_posix())
        }
    )


def hook_values(root: Path, scope: str) -> list[str]:
    if scope not in {"local", "worktree"}:
        raise RuntimeError(f"지원하지 않는 Git config scope입니다: {scope}")
    result = run_git(
        root,
        "config",
        "--null",
        f"--{scope}",
        "--get-all",
        "core.hooksPath",
        check=False,
    )
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    raw_values = result.stdout[:-1] if result.stdout.endswith(b"\0") else result.stdout
    return [item.decode("utf-8", "surrogateescape") for item in raw_values.split(b"\0")]


def previous_local_hook_values(root: Path) -> list[str]:
    return hook_values(root, "local")


def worktree_config_enabled(root: Path) -> bool:
    result = run_git(
        root,
        "config",
        "--bool",
        "--get",
        "extensions.worktreeConfig",
        check=False,
    )
    if result.returncode == 1:
        return False
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.strip() == b"true"


def current_hook_state(root: Path) -> dict[str, list[str]]:
    return {
        "local": hook_values(root, "local"),
        "worktree": hook_values(root, "worktree")
        if worktree_config_enabled(root)
        else [],
    }


def hook_config_path(root: Path, scope: str) -> Path:
    if scope not in {"local", "worktree"}:
        raise RuntimeError(f"지원하지 않는 Git config scope입니다: {scope}")
    name = "config" if scope == "local" else "config.worktree"
    return Path(
        git_text(root, "rev-parse", "--path-format=absolute", "--git-path", name)
    )


def quote_git_config_value(value: str) -> bytes:
    escaped = bytearray()
    replacements = {
        0x08: b"\\b",
        0x09: b"\\t",
        0x0A: b"\\n",
        0x22: b'\\"',
        0x5C: b"\\\\",
    }
    for byte in value.encode("utf-8", "surrogateescape"):
        replacement = replacements.get(byte)
        if replacement is not None:
            escaped.extend(replacement)
        elif byte < 0x20 or byte == 0x7F:
            raise RuntimeError("Git config 값에 지원하지 않는 제어 문자가 있습니다.")
        else:
            escaped.append(byte)
    return b'"' + bytes(escaped) + b'"'


def managed_hook_config_block(installed_hooks: str) -> bytes:
    return (
        HOOK_CONFIG_START.encode("utf-8")
        + b"\n[core]\n\thooksPath = "
        + quote_git_config_value(installed_hooks)
        + b"\n"
        + HOOK_CONFIG_END.encode("utf-8")
        + b"\n"
    )


def append_hook_config_block(original: bytes, installed_hooks: str) -> bytes:
    start = HOOK_CONFIG_START.encode("utf-8")
    end = HOOK_CONFIG_END.encode("utf-8")
    if start in original or end in original:
        raise RuntimeError("Git config에 기존 agent-project-kit marker가 있습니다.")
    separator = b"" if not original or original.endswith(b"\n") else b"\n"
    return original + separator + managed_hook_config_block(installed_hooks)


def effective_hooks_raw(root: Path) -> str | None:
    result = run_git(
        root,
        "config",
        "--null",
        "--get",
        "core.hooksPath",
        check=False,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    raw_values = result.stdout[:-1] if result.stdout.endswith(b"\0") else result.stdout
    values = raw_values.split(b"\0")
    if len(values) != 1:
        raise RuntimeError("effective core.hooksPath 값을 정확히 해석할 수 없습니다.")
    return values[0].decode("utf-8", "surrogateescape")


def effective_hooks_dir(root: Path) -> Path:
    return Path(
        git_text(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    ).resolve()


def installed_hook_effective_errors(
    worktrees: Iterable[Path], hooks_dir: Path
) -> list[str]:
    expected = hooks_dir.resolve()
    return [
        f"{worktree}: effective core.hooksPath가 설치 dispatcher와 다름"
        for worktree in worktrees
        if effective_hooks_dir(worktree) != expected
    ]


def managed_hook_activation_errors(root: Path, git_state: dict) -> list[str]:
    scope = git_state["installed_hooks_scope"]
    installed = git_state["installed_hooks_path"]
    values = current_hook_state(root)[scope]
    errors: list[str] = []
    if not values or values[-1] != installed:
        errors.append(f"{scope} core.hooksPath의 마지막 값이 설치 dispatcher가 아님")
    if effective_hooks_dir(root) != Path(installed).resolve():
        errors.append("effective core.hooksPath가 설치 dispatcher와 다름")
    return errors


def restored_hook_effective_errors(
    worktrees: Iterable[Path], installed_hooks: Path
) -> list[str]:
    installed = installed_hooks.resolve()
    return [
        f"{worktree}: 제거 뒤에도 effective core.hooksPath가 킷 경로를 가리킴"
        for worktree in worktrees
        if effective_hooks_dir(worktree) == installed
    ]


DISPATCHER_SOURCE = r'''#!/usr/bin/env python3
"""Chain the pre-install hook directory, then agent-project-kit guards."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parent
manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
name = sys.argv[1]
args = sys.argv[2:]
stdin_data = sys.stdin.buffer.read() if name == "pre-push" else None

def config_values(*options):
    completed = subprocess.run(
        ["git", "config", "--null", *options, "--get-all", "core.hooksPath"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode == 1:
        return []
    if completed.returncode:
        print("agent-project-kit: core.hooksPath 조회 실패", file=sys.stderr)
        raise SystemExit(1)
    data = completed.stdout[:-1] if completed.stdout.endswith(b"\0") else completed.stdout
    return [item.decode("utf-8", "surrogateescape") for item in data.split(b"\0")]

raw_values = config_values()
path_values = config_values("--path")
installed = manifest.get("git", {}).get("installed_hooks_path")
if not raw_values or len(raw_values) != len(path_values) or raw_values[-1] != installed:
    print("agent-project-kit: managed core.hooksPath 순서가 변경됨", file=sys.stderr)
    raise SystemExit(1)
previous = None
if len(path_values) >= 2 and path_values[-2]:
    candidate = Path(path_values[-2])
    previous = candidate if candidate.is_absolute() else Path.cwd() / candidate
elif len(path_values) == 1:
    completed = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        print("agent-project-kit: 기본 hook 경로 조회 실패", file=sys.stderr)
        raise SystemExit(1)
    data = completed.stdout.decode("utf-8", "surrogateescape")
    common = Path(data[:-1] if data.endswith("\n") else data)
    previous = common / "hooks"
if previous is not None:
    previous_hook = previous / name
    if previous_hook.exists() and previous_hook.is_file() and os.access(previous_hook, os.X_OK) and previous_hook.resolve() != (base / "hooks" / name).resolve():
        completed = subprocess.run([str(previous_hook), *args], input=stdin_data)
        if completed.returncode:
            raise SystemExit(completed.returncode)
if name in {"pre-commit", "pre-push"}:
    command = [sys.executable, "-B", str(base / "guard.py"), "git-" + name]
    completed = subprocess.run(command, input=stdin_data)
    raise SystemExit(completed.returncode)
'''


def dispatcher_files(common_root: Path, previous_hooks: Path) -> dict[str, bytes]:
    del previous_hooks  # Kept in manifest; dispatcher reads it at runtime.
    result = {"dispatcher.py": DISPATCHER_SOURCE.encode("utf-8")}
    invocation = shlex.quote(str(common_root / "dispatcher.py"))
    for hook in HOOK_NAMES:
        body = f'#!/bin/sh\nexec python3 -B {invocation} {shlex.quote(hook)} "$@"\n'
        result[f"hooks/{hook}"] = body.encode("utf-8")
    return result


def ensure_installable(
    root: Path,
    common_root: Path,
    desired_worktree: dict[str, bytes],
    desired_common: dict[str, bytes],
    old: dict | None,
    states: dict[Path, tuple[bool, bytes, int]],
) -> None:
    tracked = tracked_owned(root)
    if tracked:
        raise RuntimeError(
            "로컬 킷 목적 경로가 이미 Git에 추적 중입니다. 추적 파일은 변경하지 않습니다: "
            + ", ".join(tracked)
        )
    reserved = reserved_collisions(root, old)
    if reserved:
        raise RuntimeError(
            "킷 예약 prefix 아래 소유하지 않은 파일이 있습니다(덮어쓰지 않음): "
            + ", ".join(reserved)
        )
    common_reserved = common_reserved_collisions(common_root, old)
    if common_reserved:
        raise RuntimeError(
            "Git metadata의 킷 예약 namespace에 unowned 파일이 있습니다: "
            + ", ".join(common_reserved)
        )
    old_worktree = (old or {}).get("worktree_files", {})
    old_common = (old or {}).get("common_files", {})
    for rel in desired_worktree:
        reject_symlink_escape(root, rel)
        path = root / rel
        state = states[path]
        if state[0]:
            expected_old = old_worktree.get(rel)
            if rel in mutable_paths() and old and rel in old.get("mutable_paths", []):
                if state[2] != expected_worktree_mode(rel):
                    raise RuntimeError(f"mutable state mode가 설치값과 다릅니다: {rel}")
                continue
            if not expected_old:
                raise RuntimeError(f"기존 로컬 파일과 충돌합니다(덮어쓰지 않음): {rel}")
            if sha256_bytes(state[1]) != expected_old or state[
                2
            ] != expected_worktree_mode(rel):
                raise RuntimeError(f"설치 후 사용자가 수정한 파일입니다(보존): {rel}")
    common_parent = common_root.parent
    if common_root.is_symlink():
        raise RuntimeError(f"Git metadata 경로가 심볼릭 링크입니다: {common_root}")
    for rel in desired_common:
        reject_symlink_escape(common_parent, f"{KIT_NAME}/{rel}")
        path = common_root / rel
        state = states[path]
        if state[0]:
            expected_old = old_common.get(rel)
            if not expected_old:
                raise RuntimeError(f"기존 Git metadata와 충돌합니다: {path}")
            if sha256_bytes(state[1]) != expected_old or state[
                2
            ] != expected_common_mode(rel):
                raise RuntimeError(f"수정된 Git metadata를 덮어쓰지 않습니다: {path}")


def status_snapshot(root: Path) -> bytes:
    return run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    ).stdout


def unquote_git_path(value: bytes) -> bytes:
    if not value.startswith(b'"'):
        return value
    if len(value) < 2 or not value.endswith(b'"'):
        raise RuntimeError("Git quoted worktree 경로가 손상되었습니다.")
    source = value[1:-1]
    result = bytearray()
    escapes = {
        ord("a"): 0x07,
        ord("b"): 0x08,
        ord("t"): 0x09,
        ord("n"): 0x0A,
        ord("v"): 0x0B,
        ord("f"): 0x0C,
        ord("r"): 0x0D,
        ord('"'): ord('"'),
        ord("\\"): ord("\\"),
    }
    index = 0
    while index < len(source):
        value_byte = source[index]
        if value_byte != ord("\\"):
            result.append(value_byte)
            index += 1
            continue
        index += 1
        if index >= len(source):
            raise RuntimeError("Git quoted worktree escape가 손상되었습니다.")
        escaped = source[index]
        if escaped in escapes:
            result.append(escapes[escaped])
            index += 1
            continue
        if ord("0") <= escaped <= ord("7"):
            end = index
            while (
                end < len(source)
                and end < index + 3
                and ord("0") <= source[end] <= ord("7")
            ):
                end += 1
            result.append(int(source[index:end], 8))
            index = end
            continue
        raise RuntimeError("지원하지 않는 Git quoted worktree escape입니다.")
    return bytes(result)


def parse_worktree_porcelain(data: bytes, *, nul: bool) -> list[tuple[str, bool]]:
    records = data.split(b"\0\0" if nul else b"\n\n")
    result: list[tuple[str, bool]] = []
    for record in records:
        if not record:
            continue
        fields = record.split(b"\0" if nul else b"\n")
        worktree_fields = [field for field in fields if field.startswith(b"worktree ")]
        if len(worktree_fields) != 1:
            raise RuntimeError("linked worktree 목록을 정확히 해석할 수 없습니다.")
        raw_path = worktree_fields[0][len(b"worktree ") :]
        if not nul:
            raw_path = unquote_git_path(raw_path)
        result.append((raw_path.decode("utf-8", "surrogateescape"), b"bare" in fields))
    return result


def repository_worktree_roots(root: Path) -> tuple[list[Path], list[Path]]:
    nul = installed_git_version() >= (2, 42)
    args = (
        ("worktree", "list", "--porcelain", "-z")
        if nul
        else (
            "worktree",
            "list",
            "--porcelain",
        )
    )
    result = run_git(root, *args)
    worktrees: list[Path] = []
    bare_repositories: list[Path] = []
    for raw, bare in parse_worktree_porcelain(result.stdout, nul=nul):
        path = Path(raw)
        if not path.is_dir():
            raise RuntimeError(
                "접근할 수 없는 worktree/bare 저장소가 있어 공통 설정 영향을 검증할 수 없습니다: "
                + raw
            )
        resolved = path.resolve()
        if bare:
            bare_repositories.append(resolved)
        else:
            worktrees.append(resolved)
    if root not in worktrees:
        raise RuntimeError("현재 worktree가 Git worktree 목록에 없습니다.")
    return worktrees, bare_repositories


def same_repository_inventory(
    left: tuple[list[Path], list[Path]],
    right: tuple[list[Path], list[Path]],
) -> bool:
    return set(left[0]) == set(right[0]) and set(left[1]) == set(right[1])


def linked_worktree_roots(root: Path) -> list[Path]:
    return repository_worktree_roots(root)[0]


def sibling_worktree_collisions(root: Path, worktrees: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    exact = owned_paths()
    for sibling in worktrees:
        if sibling == root:
            continue
        tracked = tracked_owned(sibling)
        if tracked:
            errors.append(f"{sibling}: tracked/index owned path: " + ", ".join(tracked))
        existing = [
            rel
            for rel in exact
            if (sibling / rel).exists() or (sibling / rel).is_symlink()
        ]
        if existing:
            errors.append(f"{sibling}: 기존 exact owned path: " + ", ".join(existing))
        reserved = reserved_collisions(sibling, None)
        if reserved:
            errors.append(f"{sibling}: 예약 prefix 충돌: " + ", ".join(reserved))
    return errors


def ensure_all_ignored(root: Path) -> None:
    visible: list[str] = []
    for rel in owned_paths():
        result = run_git(
            root, "check-ignore", "-q", "--no-index", "--", rel, check=False
        )
        if result.returncode == 1:
            visible.append(rel)
        elif result.returncode not in {0, 1}:
            raise RuntimeError(
                "git check-ignore 실패: "
                + result.stderr.decode("utf-8", "replace").strip()
            )
    if visible:
        raise RuntimeError(
            "프로젝트 .gitignore의 재포함 규칙 때문에 로컬 파일을 숨길 수 없습니다: "
            + ", ".join(visible)
        )


def backup_files(paths: Iterable[Path]) -> dict[Path, tuple[bool, bytes, int]]:
    return {path: capture_file_state(path) for path in paths}


def restore_files(
    backups: dict[Path, tuple[bool, bytes, int]],
    post_states: dict[Path, tuple[bool, bytes, int]],
    git_config_paths: set[Path] | None = None,
) -> list[str]:
    errors: list[str] = []
    protected_configs = git_config_paths or set()
    for path, (existed, content, mode) in reversed(list(backups.items())):
        if path not in post_states:
            continue
        post_state = post_states[path]
        if not file_matches_state(path, post_state):
            errors.append(f"동시 변경 때문에 rollback하지 않은 파일: {path}")
            continue
        try:
            if existed:
                if path in protected_configs:
                    atomic_write_git_config(path, content, mode, expected=post_state)
                else:
                    atomic_write(path, content, mode, expected=post_state)
            elif post_state[0]:
                if path in protected_configs:
                    unlink_git_config(path, post_state)
                else:
                    path.unlink()
        except (OSError, RuntimeError) as error:
            errors.append(f"파일 rollback 실패 {path}: {error}")
    return errors


def install(kit_root: Path, root: Path, common: Path, mode: str) -> int:
    if root == kit_root.resolve():
        raise RuntimeError("킷 저장소 자신에게는 설치할 수 없습니다.")
    payload_dir = kit_root / "payload"
    payload = load_payload(payload_dir)
    mapping = payload_map()
    desired_worktree = {
        destination: render_worktree_file(key, payload[source_rel(key)])
        for key, destination in mapping.items()
    }
    common_root = common / KIT_NAME
    manifest_path = common_root / "manifest.json"
    hooks_dir = common_root / "hooks"
    exclude = common / "info" / "exclude"
    config_paths = {
        "local": hook_config_path(root, "local"),
        "worktree": hook_config_path(root, "worktree"),
    }
    for rel in desired_worktree:
        reject_symlink_escape(root, rel)
    for rel in common_owned_paths():
        reject_symlink_escape(common, f"{KIT_NAME}/{rel}")
    reject_symlink_escape(common, "info/exclude")
    backup_paths_list = [root / rel for rel in desired_worktree]
    backup_paths_list.extend(common_root / rel for rel in common_owned_paths())
    backup_paths_list.extend((exclude, manifest_path))
    backup_paths_list.extend(config_paths.values())
    backups = backup_files(backup_paths_list)
    old = read_manifest_state(manifest_path, backups[manifest_path])
    old_version = old["schema_version"] if old else SCHEMA_VERSION
    hook_state_before = current_hook_state(root)
    initial_effective_hooks = effective_hooks_dir(root)
    initial_hooks_raw = effective_hooks_raw(root)
    initial_worktree_config = worktree_config_enabled(root)
    if old and Path(old.get("worktree_root", "")).resolve() != root:
        raise RuntimeError(
            "linked worktree는 지원하지만 동일 Git common-dir에는 활성 설치를 하나만 둘 수 "
            "있습니다. 먼저 기존 worktree에서 --uninstall 하세요: "
            + str(old.get("worktree_root"))
        )
    if old:
        installed_scope = old["git"]["installed_hooks_scope"]
        activation_errors = managed_hook_activation_errors(root, old["git"])
        if activation_errors:
            raise RuntimeError(
                "설치 후 core.hooksPath가 변경되었습니다. 사용자의 후속 설정을 "
                "덮어쓰지 않습니다. 현재 설정을 보존하려면 먼저 --uninstall 상태를 "
                "수동 감사하세요: " + "; ".join(activation_errors)
            )
        previous_values = list(old["git"]["previous_local_hooks_paths"])
        previous_worktree_values = list(old["git"]["previous_worktree_hooks_paths"])
        previous_effective = Path(old["git"]["previous_effective_hooks_dir"])
        previous_raw = old["git"]["previous_hooks_path_raw"]
    else:
        previous_values = hook_state_before["local"]
        previous_worktree_values = hook_state_before["worktree"]
        installed_scope = "worktree" if initial_worktree_config else "local"
        previous_effective = initial_effective_hooks
        previous_raw = initial_hooks_raw
        if previous_effective == hooks_dir.resolve():
            raise RuntimeError(
                "core.hooksPath가 킷 경로를 가리키지만 manifest가 없습니다."
            )

    installed_config_path = config_paths[installed_scope]
    if old:
        config_errors = hook_config_state_errors(
            root,
            old["git"],
            file_state=backups[installed_config_path],
        )
        if config_errors:
            raise RuntimeError(
                "설치 후 hook config가 변경되었습니다. 사용자 변경을 덮어쓰지 않습니다: "
                + "; ".join(config_errors)
            )
        installed_config_state = dict(old["git"]["installed_config"])
        updated_hook_config = backups[installed_config_path][1]
        write_hook_config = False
    else:
        for path in config_paths.values():
            content = backups[path][1]
            if (
                HOOK_CONFIG_START.encode("utf-8") in content
                or HOOK_CONFIG_END.encode("utf-8") in content
            ):
                raise RuntimeError(
                    f"Git config에 원장 없는 agent-project-kit marker가 있습니다: {path}"
                )
        config_existed, config_content, config_mode = backups[installed_config_path]
        updated_hook_config = append_hook_config_block(config_content, str(hooks_dir))
        installed_config_state = {
            "path": str(installed_config_path),
            "original_existed": config_existed,
            "original_mode": config_mode,
            "original_size": len(config_content),
            "original_sha256": sha256_bytes(config_content),
            "installed_mode": config_mode,
            "installed_sha256": sha256_bytes(updated_hook_config),
        }
        write_hook_config = True

    desired_common = dispatcher_files(common_root, previous_effective)
    desired_common["guard.py"] = payload["hooks/guard.py"]
    ensure_installable(
        root,
        common_root,
        desired_worktree,
        desired_common,
        old,
        backups,
    )
    initial_inventory = repository_worktree_roots(root)
    worktrees, bare_repositories = initial_inventory
    sibling_collisions = sibling_worktree_collisions(root, worktrees)
    if sibling_collisions:
        raise RuntimeError(
            "공통 info/exclude가 다른 linked worktree의 사용자 경로를 숨길 수 있습니다: "
            + "; ".join(sibling_collisions)
        )
    if installed_scope == "local":
        if bare_repositories:
            raise RuntimeError(
                "bare 저장소와 linked worktree가 공통 local hook 설정을 공유하는 구성은 "
                "안전하게 설치할 수 없습니다. extensions.worktreeConfig=true로 전환하고 "
                "worktree별 hooksPath를 사용하세요: "
                + ", ".join(str(path) for path in bare_repositories)
            )
        if old:
            hook_effective_errors = installed_hook_effective_errors(
                worktrees, hooks_dir
            )
            if hook_effective_errors:
                raise RuntimeError("; ".join(hook_effective_errors))

    reject_symlink_escape(common, "info/exclude")
    exclude_existed, current_exclude, current_exclude_mode = backups[exclude]
    if old:
        exclude_state = dict(old["exclude"])
        exclude_errors = exclude_state_errors(
            common, exclude_state, version=old_version, file_state=backups[exclude]
        )
        if exclude_errors:
            raise RuntimeError(
                "info/exclude가 설치 후 변경되었습니다. 사용자 변경을 덮어쓰지 않습니다: "
                + "; ".join(exclude_errors)
            )
        if old_version == SCHEMA_VERSION:
            updated_exclude = current_exclude
            write_exclude = False
        else:
            # Schema upgrade: replace only the managed block. The user's original
            # prefix bytes recorded at first install are preserved verbatim.
            original_prefix = current_exclude[: exclude_state["original_size"]]
            updated_exclude = append_managed_block(original_prefix)
            exclude_state["installed_sha256"] = sha256_bytes(updated_exclude)
            write_exclude = True
    else:
        updated_exclude = append_managed_block(current_exclude)
        exclude_state = {
            "original_existed": exclude_existed,
            "original_mode": current_exclude_mode,
            "original_size": len(current_exclude),
            "original_sha256": sha256_bytes(current_exclude),
            "installed_mode": current_exclude_mode,
            "installed_sha256": sha256_bytes(updated_exclude),
        }
        write_exclude = True

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kit": KIT_NAME,
        "kit_version": KIT_VERSION,
        "install_mode": mode,
        "worktree_root": str(root),
        "git_common_dir": str(common),
        "owned_paths": owned_paths(),
        "owned_prefixes": owned_prefixes(),
        "mutable_paths": sorted(mutable_paths()),
        "mutable_files": {
            rel: (
                old.get("mutable_files", {}).get(
                    rel, sha256_bytes(desired_worktree[rel])
                )
                if old and backups[root / rel][0]
                else sha256_bytes(desired_worktree[rel])
            )
            for rel in sorted(mutable_paths())
        },
        "worktree_files": {
            rel: sha256_bytes(data)
            for rel, data in sorted(desired_worktree.items())
            if rel not in mutable_paths()
        },
        "common_files": {
            rel: sha256_bytes(data) for rel, data in sorted(desired_common.items())
        },
        "exclude_lines": exclude_lines(),
        "exclude": exclude_state,
        "git": {
            "previous_local_hooks_paths": previous_values,
            "previous_worktree_hooks_paths": previous_worktree_values,
            "previous_effective_hooks_dir": str(previous_effective),
            "previous_hooks_path_raw": previous_raw,
            "installed_hooks_scope": installed_scope,
            "installed_hooks_path": str(hooks_dir),
            "installed_config": installed_config_state,
        },
    }
    before_statuses = {worktree: status_snapshot(worktree) for worktree in worktrees}
    written_files: dict[Path, tuple[bool, bytes, int]] = {}
    expected_hook_after = {
        "local": list(hook_state_before["local"]),
        "worktree": list(hook_state_before["worktree"]),
    }
    if not old:
        expected_hook_after[installed_scope].append(str(hooks_dir))
    try:
        for rel, data in desired_worktree.items():
            path = root / rel
            if rel in mutable_paths() and backups[path][0]:
                if not file_matches_state(path, backups[path]):
                    raise RuntimeError(
                        f"설치 중 mutable state가 동시에 변경되었습니다: {path}"
                    )
                continue
            mode_bits = expected_worktree_mode(rel)
            atomic_write_recorded(path, data, mode_bits, backups[path], written_files)
        for rel, data in desired_common.items():
            path = common_root / rel
            atomic_write_recorded(path, data, 0o755, backups[path], written_files)
        if write_exclude:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_recorded(
                exclude,
                updated_exclude,
                exclude_state["installed_mode"],
                backups[exclude],
                written_files,
            )
        elif not file_matches_state(exclude, backups[exclude]):
            raise RuntimeError("설치 중 info/exclude가 동시에 변경되었습니다.")
        ensure_all_ignored(root)
        if write_hook_config:
            atomic_write_git_config_recorded(
                installed_config_path,
                updated_hook_config,
                installed_config_state["installed_mode"],
                backups[installed_config_path],
                written_files,
            )
        elif not file_matches_state(
            installed_config_path, backups[installed_config_path]
        ):
            raise RuntimeError("설치 중 hook config가 동시에 변경되었습니다.")
        manifest_data = (
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        atomic_write_recorded(
            manifest_path,
            manifest_data,
            0o600,
            backups[manifest_path],
            written_files,
        )
        if (
            current_hook_state(root) != expected_hook_after
            or effective_hooks_dir(root) != hooks_dir.resolve()
        ):
            raise RuntimeError(
                "core.hooksPath의 상위 우선순위 설정 때문에 Git guard를 활성화할 수 없습니다."
            )
        if installed_scope == "local":
            effective_errors = installed_hook_effective_errors(worktrees, hooks_dir)
            if effective_errors:
                raise RuntimeError("; ".join(effective_errors))
        final_inventory = repository_worktree_roots(root)
        if not same_repository_inventory(initial_inventory, final_inventory):
            raise RuntimeError(
                "설치 중 linked worktree/bare 저장소 목록이 변경되었습니다. "
                "공통 exclude/hook 영향을 재검증할 수 없어 rollback합니다."
            )
        final_worktrees, final_bare_repositories = final_inventory
        final_collisions = sibling_worktree_collisions(root, final_worktrees)
        if final_collisions:
            raise RuntimeError(
                "설치 중 sibling worktree에 충돌 경로가 생겼습니다: "
                + "; ".join(final_collisions)
            )
        if installed_scope == "local":
            if final_bare_repositories:
                raise RuntimeError(
                    "설치 중 bare 저장소가 추가되어 local hook 공유가 안전하지 않습니다."
                )
            effective_errors = installed_hook_effective_errors(
                final_worktrees, hooks_dir
            )
            if effective_errors:
                raise RuntimeError("; ".join(effective_errors))
        after_statuses = {
            worktree: status_snapshot(worktree) for worktree in final_worktrees
        }
        if after_statuses != before_statuses:
            raise RuntimeError(
                "설치 전후 어느 linked worktree의 git status가 달라졌습니다. "
                "모든 설치 변경을 rollback합니다."
            )
    except BaseException as original_error:
        rollback_errors = restore_files(
            backups, written_files, set(config_paths.values())
        )
        if rollback_errors:
            raise RuntimeError(
                "설치 rollback이 완전하지 않습니다. 수동 감사 필요: "
                + "; ".join(rollback_errors)
            ) from original_error
        raise

    print(f"설치 완료 ({mode}): {root}")
    print(
        "  Claude Code: CLAUDE.local.md + .claude/skills/agent-kit-* + .claude/agents/*"
    )
    print(
        "  Codex:       AGENTS.override.md + .agents/skills/agent-kit-* + .codex/agents/*"
    )
    print(
        "  공통 상태:   .agent-project-kit/CONTEXT.md, HANDOFF.md, AGENT-RULES.md, templates/"
    )
    print(
        "이 파일들은 Git 로컬 exclude와 commit/push guard로 보호됩니다. stage/commit하지 마세요."
    )
    print(
        "다음: 에이전트를 열고 agent-kit-init(신규) 또는 agent-kit-adopt(편입) 스킬로 "
        "인터뷰를 진행해 AGENTS.md(canonical)와 포인터 CLAUDE.md를 만들거나 병합하세요."
    )
    return 0


def check_hashes(
    base: Path,
    entries: dict[str, str],
    label: str,
    expected_mode: Callable[[str], int],
) -> list[str]:
    errors: list[str] = []
    for rel, expected in sorted(entries.items()):
        try:
            reject_symlink_escape(base, rel)
        except RuntimeError as error:
            errors.append(f"{label} 안전하지 않은 경로: {error}")
            continue
        path = base / rel
        if not path.is_file():
            errors.append(f"{label} 누락: {rel}")
        elif sha256_file(path) != expected:
            errors.append(f"{label} 변조/드리프트: {rel}")
        elif stat.S_IMODE(path.stat().st_mode) != expected_mode(rel):
            errors.append(f"{label} mode 드리프트: {rel}")
    return errors


def block_is_exact(exclude: Path, version: int | None = None) -> bool:
    if not exclude.is_file() or exclude.is_symlink():
        return False
    data = exclude.read_bytes()
    start = BLOCK_START.encode("utf-8")
    end = BLOCK_END.encode("utf-8")
    expected = expected_exclude_block(version).encode("utf-8")
    if data.count(start) != 1 or data.count(end) != 1:
        return False
    return data.count(expected) == 1


def exclude_state_errors(
    common: Path,
    state: dict,
    *,
    version: int | None = None,
    file_state: tuple[bool, bytes, int] | None = None,
) -> list[str]:
    exclude = common / "info" / "exclude"
    errors: list[str] = []
    try:
        reject_symlink_escape(common, "info/exclude")
    except RuntimeError as error:
        return [str(error)]
    if file_state is None:
        try:
            file_state = capture_file_state(exclude)
        except RuntimeError as error:
            return [str(error)]
    if not file_state[0]:
        return ["info/exclude 누락 또는 비정상 파일"]
    data = file_state[1]
    mode = file_state[2]
    if sha256_bytes(data) != state["installed_sha256"]:
        errors.append("info/exclude가 설치 후 변경됨")
    if mode != state["installed_mode"]:
        errors.append("info/exclude mode가 설치 후 변경됨")
    size = state["original_size"]
    if size > len(data):
        errors.append("info/exclude 원본 크기 원장이 손상됨")
        return errors
    original = data[:size]
    if sha256_bytes(original) != state["original_sha256"]:
        errors.append("info/exclude 원본 prefix가 설치 원장과 다름")
    try:
        expected = append_managed_block(original, version)
    except RuntimeError as error:
        errors.append(str(error))
    else:
        if data != expected:
            errors.append("info/exclude managed block 경계가 설치 원장과 다름")
    expected_block = expected_exclude_block(version).encode("utf-8")
    start = BLOCK_START.encode("utf-8")
    end = BLOCK_END.encode("utf-8")
    if (
        data.count(start) != 1
        or data.count(end) != 1
        or data.count(expected_block) != 1
    ):
        errors.append("info/exclude managed block 누락/변조")
    return errors


def hook_config_state_errors(
    root: Path,
    git_state: dict,
    *,
    file_state: tuple[bool, bytes, int] | None = None,
) -> list[str]:
    state = git_state["installed_config"]
    scope = git_state["installed_hooks_scope"]
    expected_path = hook_config_path(root, scope)
    if state["path"] != str(expected_path):
        return ["설치된 hook config 경로가 현재 Git metadata 경로와 다름"]
    if file_state is None:
        try:
            file_state = capture_file_state(expected_path)
        except RuntimeError as error:
            return [str(error)]
    if not file_state[0]:
        return ["설치된 hook config 파일이 누락됨"]
    data = file_state[1]
    mode = file_state[2]
    errors: list[str] = []
    if sha256_bytes(data) != state["installed_sha256"]:
        errors.append("설치 후 hook config bytes가 변경됨")
    if mode != state["installed_mode"]:
        errors.append("설치 후 hook config mode가 변경됨")
    size = state["original_size"]
    if size > len(data):
        errors.append("hook config 원본 크기 원장이 손상됨")
        return errors
    original = data[:size]
    if sha256_bytes(original) != state["original_sha256"]:
        errors.append("hook config 원본 prefix가 설치 원장과 다름")
        return errors
    try:
        expected = append_hook_config_block(original, git_state["installed_hooks_path"])
    except RuntimeError as error:
        errors.append(str(error))
    else:
        if data != expected:
            errors.append("hook config managed block 경계가 설치 원장과 다름")
    return errors


def inspect(kit_root: Path, root: Path, common: Path, verbose: bool) -> int:
    common_root = common / KIT_NAME
    manifest = read_manifest(common_root / "manifest.json", required=True)
    assert manifest is not None
    errors: list[str] = []
    worktrees: list[Path] = []
    bare_repositories: list[Path] = []
    try:
        worktrees, bare_repositories = repository_worktree_roots(root)
        errors.extend(sibling_worktree_collisions(root, worktrees))
    except RuntimeError as error:
        errors.append(str(error))
    if Path(manifest.get("worktree_root", "")).resolve() != root:
        errors.append("manifest worktree_root가 현재 저장소와 다름")
    if manifest.get("kit_version") != KIT_VERSION:
        errors.append(
            f"설치 버전({manifest.get('kit_version')})과 현재 킷({KIT_VERSION})이 다름"
        )
    errors.extend(
        check_hashes(
            root,
            manifest.get("worktree_files", {}),
            "worktree",
            expected_worktree_mode,
        )
    )
    errors.extend(
        check_hashes(
            common_root,
            manifest.get("common_files", {}),
            "git metadata",
            expected_common_mode,
        )
    )
    payload = load_payload(kit_root / "payload")
    for key, rel in payload_map().items():
        if rel in mutable_paths():
            continue
        path = root / rel
        if path.is_file() and sha256_file(path) != sha256_bytes(
            render_worktree_file(key, payload[source_rel(key)])
        ):
            errors.append(f"현재 킷 payload와 설치본이 다름(재설치 필요): {rel}")
    desired_common = dispatcher_files(
        common_root,
        Path(manifest.get("git", {}).get("previous_effective_hooks_dir", ".")),
    )
    desired_common["guard.py"] = payload["hooks/guard.py"]
    for rel, data in desired_common.items():
        path = common_root / rel
        if path.is_file() and sha256_file(path) != sha256_bytes(data):
            errors.append(f"현재 킷 runtime과 설치본이 다름(재설치 필요): {rel}")
    for rel in manifest.get("mutable_paths", []):
        path = root / rel
        if not path.is_file() or path.is_symlink():
            errors.append(f"mutable state 누락/비정상: {rel}")
        elif stat.S_IMODE(path.stat().st_mode) != expected_worktree_mode(rel):
            errors.append(f"mutable state mode 드리프트: {rel}")
    if tracked_owned(root):
        errors.append("로컬 킷 파일이 Git에 추적됨: " + ", ".join(tracked_owned(root)))
    reserved = reserved_collisions(root, manifest)
    if reserved:
        errors.append("예약 prefix의 unowned 파일: " + ", ".join(reserved))
    common_reserved = common_reserved_collisions(common_root, manifest)
    if common_reserved:
        errors.append(
            "Git metadata 예약 namespace의 unowned 파일: " + ", ".join(common_reserved)
        )
    errors.extend(
        exclude_state_errors(
            common, manifest["exclude"], version=manifest["schema_version"]
        )
    )
    errors.extend(hook_config_state_errors(root, manifest["git"]))
    try:
        ensure_all_ignored(root)
    except RuntimeError as error:
        errors.append(str(error))
    installed_scope = manifest["git"]["installed_hooks_scope"]
    errors.extend(managed_hook_activation_errors(root, manifest["git"]))
    if installed_scope == "local" and worktrees:
        errors.extend(installed_hook_effective_errors(worktrees, common_root / "hooks"))
    if installed_scope == "local" and bare_repositories:
        errors.append(
            "bare 저장소와 linked worktree가 공통 local hook 설정을 공유해 "
            "설치 안전성을 보장할 수 없음"
        )
    try:
        json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))
        json.loads((root / ".codex/hooks.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"provider hook JSON 오류: {error}")
    for skill in SCHEMA_SKILLS[SCHEMA_VERSION]:
        left = root / f".agents/skills/agent-kit-{skill}/SKILL.md"
        right = root / f".claude/skills/agent-kit-{skill}/SKILL.md"
        if (
            left.is_file()
            and right.is_file()
            and left.read_bytes() != right.read_bytes()
        ):
            errors.append(f"provider skill 내용 불일치: agent-kit-{skill}")
    if verbose:
        print(f"agent-project-kit doctor: {root}")
    if errors:
        for item in errors:
            print(f"  ERROR: {item}")
        return 1
    print("  OK: manifest/hash, local exclude, provider adapters, Git dispatcher")
    return 0


def uninstall(root: Path, common: Path) -> int:
    common_root = common / KIT_NAME
    manifest_path = common_root / "manifest.json"
    exclude = common / "info" / "exclude"
    config_paths = {
        "local": hook_config_path(root, "local"),
        "worktree": hook_config_path(root, "worktree"),
    }
    removal_paths = [exclude, manifest_path]
    removal_paths.extend(
        root / rel for rel in owned_paths() if rel not in mutable_paths()
    )
    removal_paths.extend(common_root / rel for rel in common_owned_paths())
    removal_paths.extend(root / rel for rel in sorted(mutable_paths()))
    byproduct_files = runtime_byproduct_files(root, common_root)
    removal_paths.extend(byproduct_files)
    removal_paths.extend(config_paths.values())
    for rel in owned_paths():
        reject_symlink_escape(root, rel)
    for rel in common_owned_paths():
        reject_symlink_escape(common, f"{KIT_NAME}/{rel}")
    reject_symlink_escape(common, "info/exclude")
    backups = backup_files(removal_paths)
    manifest = read_manifest_state(manifest_path, backups[manifest_path], required=True)
    assert manifest is not None
    if Path(manifest.get("worktree_root", "")).resolve() != root:
        raise RuntimeError("manifest의 worktree와 대상이 달라 uninstall을 중단합니다.")
    warnings: list[str] = []
    initial_inventory = repository_worktree_roots(root)
    worktrees, bare_repositories = initial_inventory
    warnings.extend(sibling_worktree_collisions(root, worktrees))
    tracked = tracked_owned(root)
    if tracked:
        warnings.append(
            "로컬 킷 파일이 Git index/tracking에 포함됨: " + ", ".join(tracked)
        )
    common_reserved = common_reserved_collisions(common_root, manifest)
    if common_reserved:
        warnings.append(
            "Git metadata 예약 namespace의 unowned 파일: " + ", ".join(common_reserved)
        )
    installed_scope = manifest["git"]["installed_hooks_scope"]
    installed_config_path = config_paths[installed_scope]
    installed_hook_state = current_hook_state(root)
    warnings.extend(managed_hook_activation_errors(root, manifest["git"]))
    if installed_scope == "local":
        warnings.extend(
            installed_hook_effective_errors(worktrees, common_root / "hooks")
        )
        if bare_repositories:
            warnings.append(
                "bare 저장소가 local hook 설정을 공유하는 설치는 안전하지 않음"
            )
    warnings.extend(
        exclude_state_errors(
            common,
            manifest["exclude"],
            version=manifest["schema_version"],
            file_state=backups[exclude],
        )
    )
    warnings.extend(
        hook_config_state_errors(
            root,
            manifest["git"],
            file_state=backups[installed_config_path],
        )
    )
    for base, key, mode_for in (
        (root, "worktree_files", expected_worktree_mode),
        (common_root, "common_files", expected_common_mode),
    ):
        for rel, expected in sorted(manifest.get(key, {}).items()):
            try:
                reject_symlink_escape(base, rel)
            except RuntimeError as error:
                warnings.append(str(error))
                continue
            path = base / rel
            file_state = backups[path]
            if not file_state[0]:
                continue
            if sha256_bytes(file_state[1]) != expected or file_state[2] != mode_for(
                rel
            ):
                warnings.append(f"수정된 소유 파일 보존: {path}")
    for rel in manifest.get("mutable_paths", []):
        try:
            reject_symlink_escape(root, rel)
        except RuntimeError as error:
            warnings.append(str(error))
            continue
        path = root / rel
        file_state = backups[path]
        if file_state[0]:
            baseline = manifest.get("mutable_files", {}).get(rel)
            if (
                not baseline
                or sha256_bytes(file_state[1]) != baseline
                or file_state[2] != expected_worktree_mode(rel)
            ):
                warnings.append(f"사용자가 갱신한 mutable state 보존: {path}")
    if warnings:
        for item in warnings:
            print(f"  WARNING: {item}", file=sys.stderr)
        print(
            "uninstall 중단: 어떤 파일이나 설정도 제거하지 않았습니다.", file=sys.stderr
        )
        return 1

    before_statuses = {worktree: status_snapshot(worktree) for worktree in worktrees}
    post_states: dict[Path, tuple[bool, bytes, int]] = {}
    removed_mutable = 0
    try:
        if current_hook_state(root) != installed_hook_state:
            raise RuntimeError(
                "제거 중 core.hooksPath가 동시에 변경되어 사용자 설정을 보존하고 중단합니다."
            )
        config_state = manifest["git"]["installed_config"]
        original_config = backups[installed_config_path][1][
            : config_state["original_size"]
        ]
        if config_state["original_existed"]:
            atomic_write_git_config_recorded(
                installed_config_path,
                original_config,
                config_state["original_mode"],
                backups[installed_config_path],
                post_states,
            )
        else:
            unlink_git_config_recorded(
                installed_config_path,
                backups[installed_config_path],
                post_states,
            )
        restored_errors = restored_hook_effective_errors(
            worktrees, common_root / "hooks"
        )
        if restored_errors:
            raise RuntimeError(
                "기존 hook config 복원 실패: " + "; ".join(restored_errors)
            )
        exclude_state = manifest["exclude"]
        original_exclude = backups[exclude][1][: exclude_state["original_size"]]
        if exclude_state["original_existed"]:
            atomic_write_recorded(
                exclude,
                original_exclude,
                exclude_state["original_mode"],
                backups[exclude],
                post_states,
            )
        else:
            unlink_recorded(exclude, backups[exclude], post_states)
        for base, key in ((root, "worktree_files"), (common_root, "common_files")):
            for rel in sorted(manifest[key], reverse=True):
                path = base / rel
                if backups[path][0]:
                    unlink_recorded(path, backups[path], post_states)
        for rel in sorted(manifest["mutable_paths"], reverse=True):
            path = root / rel
            if backups[path][0]:
                unlink_recorded(path, backups[path], post_states)
                removed_mutable += 1
        # Kit-caused byproducts (pycache/.DS_Store/stale locks) would surface in
        # git status once the managed exclude is restored; remove them too.
        for path in byproduct_files:
            if backups[path][0]:
                unlink_recorded(path, backups[path], post_states)
        unlink_recorded(manifest_path, backups[manifest_path], post_states)
        final_inventory = repository_worktree_roots(root)
        if not same_repository_inventory(initial_inventory, final_inventory):
            raise RuntimeError(
                "제거 중 linked worktree/bare 저장소 목록이 변경되었습니다. rollback합니다."
            )
        final_worktrees, _ = final_inventory
        final_collisions = sibling_worktree_collisions(root, final_worktrees)
        if final_collisions:
            raise RuntimeError(
                "제거 중 sibling worktree에 충돌 경로가 생겼습니다: "
                + "; ".join(final_collisions)
            )
        restored_errors = restored_hook_effective_errors(
            final_worktrees, common_root / "hooks"
        )
        if restored_errors:
            raise RuntimeError(
                "제거 후 hook config 복원 실패: " + "; ".join(restored_errors)
            )
        after_statuses = {
            worktree: status_snapshot(worktree) for worktree in final_worktrees
        }
        if after_statuses != before_statuses:
            raise RuntimeError(
                "제거 전후 어느 linked worktree의 git status가 달라졌습니다."
            )
    except BaseException as original_error:
        rollback_errors = restore_files(
            backups, post_states, set(config_paths.values())
        )
        if rollback_errors:
            raise RuntimeError(
                "uninstall rollback이 완전하지 않습니다. 수동 감사 필요: "
                + "; ".join(rollback_errors)
            ) from original_error
        raise

    print(f"uninstall 완료: {root}")
    if removed_mutable:
        print(
            f"  명시적 uninstall 정책에 따라 mutable local state {removed_mutable}개를 제거했습니다."
        )
    return 0


def usage(program: str) -> str:
    return f"""사용법:
  {program} <Git 프로젝트 경로>             신규 로컬 설치
  {program} --adopt <Git 프로젝트 경로>     진행 중 프로젝트 로컬 편입
  {program} --doctor <Git 프로젝트 경로>    무결성 점검(읽기 전용)
  {program} --diff <Git 프로젝트 경로>      설치 드리프트 점검(읽기 전용)
  {program} --uninstall <Git 프로젝트 경로> 로컬 킷 제거/훅 설정 복원
"""


def parse_args(argv: list[str]) -> tuple[str, str]:
    if not argv or argv[0] in {"-h", "--help"}:
        print(usage(Path(sys.argv[0]).name))
        raise SystemExit(0 if argv else 2)
    mode = "install"
    if argv[0] in {"--adopt", "--doctor", "--diff", "--uninstall"}:
        mode = argv.pop(0)[2:]
    if len(argv) != 1:
        raise RuntimeError(usage(Path(sys.argv[0]).name).rstrip())
    return mode, argv[0]


def main(argv: list[str] | None = None) -> int:
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        mode, requested = parse_args(args)
        ensure_git_version()
        root, common = find_repository(requested)
        kit_root = Path(__file__).resolve().parent.parent
        with common_directory_lock(
            common, create=mode in {"install", "adopt", "uninstall"}
        ):
            if mode in {"install", "adopt"}:
                return install(kit_root, root, common, mode)
            if mode in {"doctor", "diff"}:
                return inspect(kit_root, root, common, verbose=mode == "doctor")
            return uninstall(root, common)
    except (OSError, RuntimeError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
