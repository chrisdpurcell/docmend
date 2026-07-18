"""Build an installed-wheel qualification candidate from one exact Git commit.

The Git object bytes, archive, wheel, and installed imports are all bound to
one immutable ``HEAD``.  Private build paths and command output never belong in
public scale evidence; callers receive only the provenance needed to construct
the public candidate record.
"""

import fcntl
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
import tomllib
import weakref
import zipfile
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from email.parser import BytesParser
from pathlib import Path
from typing import Literal, Protocol, cast

QUALIFICATION_UV_VERSION = "0.11.6"
_BUILD_BACKEND = "uv_build"
_BUILD_REQUIREMENT = f"{_BUILD_BACKEND}=={QUALIFICATION_UV_VERSION}"
_UV_VERSION = re.compile(r"^uv ([0-9]+(?:\.[0-9]+){2})(?:[ \n]|$)")
type BuildFailureKind = Literal["build", "install", "provenance"]


class BuildContractError(Exception):
    """Candidate source or build output violates the qualification contract."""

    def __init__(
        self,
        message: str,
        *,
        failure_kind: BuildFailureKind = "build",
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.wheel_sha256: str | None = None
        self.workspace_lease: CandidateWorkspaceLease | None = None

    def with_checkpoint(
        self,
        *,
        wheel_sha256: str | None,
        workspace_lease: CandidateWorkspaceLease,
    ) -> BuildContractError:
        self.wheel_sha256 = wheel_sha256
        self.workspace_lease = workspace_lease
        return self


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result from one fixed-argv private build command."""

    returncode: int
    stdout: bytes
    stderr: bytes


class CommandService(Protocol):
    """Typed command boundary used by source inspection and candidate builds."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        pass_fds: Sequence[int] = (),
    ) -> CommandResult: ...


class _Finalizer(Protocol):
    """Structural surface retained from ``weakref.finalize``."""

    @property
    def alive(self) -> bool: ...

    def __call__(self) -> object | None: ...


@dataclass(frozen=True, slots=True)
class _SubprocessCommands:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        pass_fds: Sequence[int] = (),
    ) -> CommandResult:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=environment,
            check=False,
            capture_output=True,
            pass_fds=tuple(pass_fds),
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


_DEFAULT_COMMANDS = _SubprocessCommands()


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """Immutable identity and committed dependency inputs for one candidate."""

    repository: Path
    commit: str
    package_name: str
    package_version: str
    build_backend: str
    build_backend_version: str
    build_frontend_version: str
    pyproject_sha256: str
    lock_sha256: str
    pyproject_bytes: bytes
    lock_bytes: bytes


@dataclass(frozen=True, slots=True)
class BuildRequest:
    """Private locations and exact interpreter used for one candidate build."""

    repository: Path
    workspace: Path
    python_executable: Path


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CandidateWorkspaceLease:
    """Held private workspace identity retained through evidence publication."""

    path: Path
    descriptor: int = field(repr=False)
    _finalizer: _Finalizer = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        finalizer = weakref.finalize(self, os.close, self.descriptor)
        object.__setattr__(self, "_finalizer", finalizer)

    @property
    def held_path(self) -> Path:
        if not self._finalizer.alive:
            raise BuildContractError("candidate workspace identity is closed")
        return Path(f"/proc/self/fd/{self.descriptor}")

    def require_current_identity(self) -> os.stat_result:
        if not self._finalizer.alive:
            raise BuildContractError("candidate workspace identity is closed")
        try:
            held = os.fstat(self.descriptor)
            current = self.path.lstat()
            resolved = self.path.resolve(strict=True)
        except OSError as exc:
            raise BuildContractError("candidate workspace identity became unavailable") from exc
        if (
            not stat.S_ISDIR(held.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino)
            or stat.S_IMODE(held.st_mode) != 0o700
            or stat.S_IMODE(current.st_mode) != 0o700
            or resolved != self.path
        ):
            raise BuildContractError("candidate workspace identity changed")
        return held

    def close(self) -> None:
        self._finalizer()


@dataclass(frozen=True, slots=True)
class _ArtifactPathSnapshot:
    """Lexical binding and content identity for one later path consumer."""

    kind: str
    path: Path
    resolved_path: Path
    lexical_device: int
    lexical_inode: int
    lexical_size: int
    lexical_mode: int
    lexical_mtime_ns: int
    target_device: int
    target_inode: int
    target_size: int
    target_mode: int
    target_mtime_ns: int
    target_sha256: str


@dataclass(frozen=True, slots=True)
class CandidateArtifactLease:
    """Reconciled snapshots for the three installed-candidate consumers.

    These snapshots detect permanent substitutions before and after each
    consumer. They intentionally do not claim descriptor-bound execution: a
    same-user swap-and-restore wholly between adjacent checks is an ABA limit
    of the current Task 5 pathname-based process contract.
    """

    executable: _ArtifactPathSnapshot
    venv_python: _ArtifactPathSnapshot
    measurement_wrapper: _ArtifactPathSnapshot

    @classmethod
    def capture(
        cls,
        *,
        executable: Path,
        venv_python: Path,
        measurement_wrapper: Path,
    ) -> CandidateArtifactLease:
        return cls(
            executable=_snapshot_artifact_path(
                executable,
                kind="candidate executable",
                allow_symlink=False,
                executable=True,
            ),
            venv_python=_snapshot_artifact_path(
                venv_python,
                kind="candidate Python",
                allow_symlink=True,
                executable=True,
            ),
            measurement_wrapper=_snapshot_artifact_path(
                measurement_wrapper,
                kind="candidate measurement wrapper",
                allow_symlink=False,
                executable=False,
            ),
        )

    def require_current_identity(self) -> None:
        for snapshot, allow_symlink, executable in (
            (self.executable, False, True),
            (self.venv_python, True, True),
            (self.measurement_wrapper, False, False),
        ):
            _require_artifact_snapshot(
                snapshot,
                allow_symlink=allow_symlink,
                executable=executable,
            )


@dataclass(frozen=True, slots=True)
class CandidateBuild:
    """Installed-wheel candidate and its reconciled private identities."""

    commit: str
    package_name: str
    package_version: str
    build_backend_version: str
    build_frontend_version: str
    source_snapshot: Path
    wheel: Path
    wheel_sha256: str
    venv: Path
    venv_python: Path
    executable: Path
    workspace_lease: CandidateWorkspaceLease
    artifact_lease: CandidateArtifactLease

    def require_current_identity(self) -> None:
        self.workspace_lease.require_current_identity()
        self.artifact_lease.require_current_identity()


@dataclass(frozen=True, slots=True)
class _RegularFileSnapshot:
    path: Path
    data: bytes
    device: int
    inode: int
    size: int
    mode: int
    mtime_ns: int


def _private_environment(private_home: Path | None = None) -> dict[str, str]:
    # The fixed allowlist excludes inherited package-manager configuration,
    # Python instrumentation, dynamic-loader hooks, and credential material.
    environment = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": str(private_home) if private_home is not None else os.devnull,
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", os.defpath),
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
    }
    if private_home is not None:
        environment.update(
            {
                "TMPDIR": str(private_home / "tmp"),
                "XDG_CACHE_HOME": str(private_home / "cache"),
                "XDG_CONFIG_HOME": str(private_home / "config"),
                "XDG_STATE_HOME": str(private_home / "state"),
            }
        )
    return environment


def _run(
    commands: CommandService,
    argv: Sequence[str],
    *,
    cwd: Path,
    kind: str,
    private_home: Path | None = None,
    pass_fds: Sequence[int] = (),
    failure_kind: BuildFailureKind = "build",
) -> bytes:
    try:
        result = commands.run(
            argv,
            cwd=cwd,
            environment=_private_environment(private_home),
            pass_fds=pass_fds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BuildContractError(f"{kind} failed", failure_kind=failure_kind) from exc
    if result.returncode != 0:
        raise BuildContractError(f"{kind} failed", failure_kind=failure_kind)
    return result.stdout


def _text(raw: bytes, *, field: str) -> str:
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise BuildContractError(f"{field} must be UTF-8 text") from exc


def _digest(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _snapshot_artifact_path(
    path: Path,
    *,
    kind: str,
    allow_symlink: bool,
    executable: bool,
) -> _ArtifactPathSnapshot:
    """Capture both a consumer pathname and the regular file it resolves to."""

    descriptor: int | None = None
    try:
        lexical = path.lstat()
        is_symlink = stat.S_ISLNK(lexical.st_mode)
        if is_symlink:
            if not allow_symlink:
                raise BuildContractError(
                    f"{kind} must be a regular non-symlink file",
                    failure_kind="install",
                )
        elif not stat.S_ISREG(lexical.st_mode):
            raise BuildContractError(
                f"{kind} must be a regular file or approved symlink",
                failure_kind="install",
            )
        resolved = path.resolve(strict=True)
        descriptor = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        target_before = os.fstat(descriptor)
        if not stat.S_ISREG(target_before.st_mode) or (
            executable and target_before.st_mode & 0o111 == 0
        ):
            raise BuildContractError(
                f"{kind} must resolve to a regular executable"
                if executable
                else f"{kind} must resolve to a regular file",
                failure_kind="install",
            )
        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        target_after = os.fstat(descriptor)
        lexical_after = path.lstat()
        resolved_after = path.resolve(strict=True)
    except OSError as exc:
        raise BuildContractError(
            f"{kind} identity is unavailable",
            failure_kind="install",
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    lexical_identity = (
        lexical.st_dev,
        lexical.st_ino,
        lexical.st_size,
        lexical.st_mode,
        lexical.st_mtime_ns,
    )
    if (
        lexical_identity
        != (
            lexical_after.st_dev,
            lexical_after.st_ino,
            lexical_after.st_size,
            lexical_after.st_mode,
            lexical_after.st_mtime_ns,
        )
        or resolved_after != resolved
        or (
            target_before.st_dev,
            target_before.st_ino,
            target_before.st_size,
            target_before.st_mode,
            target_before.st_mtime_ns,
        )
        != (
            target_after.st_dev,
            target_after.st_ino,
            target_after.st_size,
            target_after.st_mode,
            target_after.st_mtime_ns,
        )
        or (
            not is_symlink
            and (lexical.st_dev, lexical.st_ino) != (target_after.st_dev, target_after.st_ino)
        )
    ):
        raise BuildContractError(f"{kind} identity changed", failure_kind="install")
    return _ArtifactPathSnapshot(
        kind=kind,
        path=path,
        resolved_path=resolved,
        lexical_device=lexical.st_dev,
        lexical_inode=lexical.st_ino,
        lexical_size=lexical.st_size,
        lexical_mode=lexical.st_mode,
        lexical_mtime_ns=lexical.st_mtime_ns,
        target_device=target_after.st_dev,
        target_inode=target_after.st_ino,
        target_size=target_after.st_size,
        target_mode=target_after.st_mode,
        target_mtime_ns=target_after.st_mtime_ns,
        target_sha256=f"sha256:{digest.hexdigest()}",
    )


def _require_artifact_snapshot(
    snapshot: _ArtifactPathSnapshot,
    *,
    allow_symlink: bool,
    executable: bool,
) -> None:
    """Fail closed when a later pathname no longer names the bound artifact."""

    try:
        current = _snapshot_artifact_path(
            snapshot.path,
            kind=snapshot.kind,
            allow_symlink=allow_symlink,
            executable=executable,
        )
    except BuildContractError as exc:
        raise BuildContractError(
            f"{snapshot.kind} identity changed",
            failure_kind="install",
        ) from exc
    if current != snapshot:
        raise BuildContractError(
            f"{snapshot.kind} identity changed",
            failure_kind="install",
        )


@contextmanager
def _sealed_input(data: bytes, *, name: str) -> Generator[tuple[Path, int]]:
    """Expose immutable bytes to a child through one inherited Linux memfd."""

    try:
        descriptor = os.memfd_create(name, os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    except OSError as exc:
        raise BuildContractError(
            "sealed installer input is unavailable",
            failure_kind="install",
        ) from exc
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written == 0:
                raise BuildContractError(
                    "sealed installer input write made no progress",
                    failure_kind="install",
                )
            remaining = remaining[written:]
        os.fchmod(descriptor, 0o400)
        fcntl.fcntl(
            descriptor,
            fcntl.F_ADD_SEALS,
            fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE,
        )
        yield Path(f"/proc/self/fd/{descriptor}"), descriptor
    except OSError as exc:
        raise BuildContractError(
            "sealed installer input is unavailable",
            failure_kind="install",
        ) from exc
    finally:
        os.close(descriptor)


def _real_repository(repository: Path) -> Path:
    if not repository.is_absolute():
        repository = repository.absolute()
    try:
        metadata = repository.lstat()
        resolved = repository.resolve(strict=True)
    except OSError as exc:
        raise BuildContractError("candidate repository must be an existing directory") from exc
    if repository.is_symlink() or not repository.is_dir() or not resolved.samefile(repository):
        raise BuildContractError("candidate repository must be a real directory")
    if not metadata.st_mode:
        raise BuildContractError("candidate repository identity is unavailable")
    return resolved


def _head(commands: CommandService, repository: Path) -> str:
    raw = _run(
        commands,
        ("git", "rev-parse", "--verify", "HEAD^{commit}"),
        cwd=repository,
        kind="candidate HEAD (repository may be unborn)",
    )
    commit = _text(raw, field="candidate HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise BuildContractError("candidate HEAD must identify one commit")
    return commit


def _require_clean(commands: CommandService, repository: Path) -> None:
    raw = _run(
        commands,
        ("git", "status", "--porcelain=v2", "--untracked-files=all"),
        cwd=repository,
        kind="candidate clean-tree check",
    )
    if raw:
        raise BuildContractError(
            "candidate repository must have a clean tracked and untracked tree"
        )


def _object_bytes(
    commands: CommandService,
    repository: Path,
    commit: str,
    name: str,
) -> bytes:
    return _run(
        commands,
        ("git", "show", f"{commit}:{name}"),
        cwd=repository,
        kind=f"committed {name} read",
    )


def _frontend_version(commands: CommandService, repository: Path) -> str:
    output = _text(
        _run(commands, ("uv", "--version"), cwd=repository, kind="uv version check"),
        field="uv version",
    )
    matched = _UV_VERSION.match(output)
    if matched is None or matched.group(1) != QUALIFICATION_UV_VERSION:
        raise BuildContractError(f"qualification requires exact uv {QUALIFICATION_UV_VERSION}")
    return matched.group(1)


def _project_contract(pyproject_bytes: bytes) -> tuple[str, str, str, str]:
    try:
        document = tomllib.loads(pyproject_bytes.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise BuildContractError("committed pyproject.toml must be valid UTF-8 TOML") from exc
    project = document.get("project")
    build_system = document.get("build-system")
    if type(project) is not dict or type(build_system) is not dict:
        raise BuildContractError("pyproject must define project and build-system tables")
    project_values = cast("dict[object, object]", project)
    build_values = cast("dict[object, object]", build_system)
    name = project_values.get("name")
    version = project_values.get("version")
    backend = build_values.get("build-backend")
    requirements = build_values.get("requires")
    if name != "docmend" or type(version) is not str or not version:
        raise BuildContractError("candidate package must be docmend with a static version")
    if backend != _BUILD_BACKEND:
        raise BuildContractError(f"candidate build backend must be {_BUILD_BACKEND}")
    if requirements != [_BUILD_REQUIREMENT]:
        raise BuildContractError(
            f"candidate build requirements must contain exactly {_BUILD_REQUIREMENT}"
        )
    return (
        cast("str", name),
        version,
        cast("str", backend),
        QUALIFICATION_UV_VERSION,
    )


def inspect_candidate_source(
    repository: Path,
    *,
    commands: CommandService = _DEFAULT_COMMANDS,
) -> SourceProvenance:
    """Bind one clean repository, exact commit, and committed build inputs."""

    root = _real_repository(repository)
    top_level = _text(
        _run(
            commands,
            ("git", "rev-parse", "--show-toplevel"),
            cwd=root,
            kind="candidate repository check",
        ),
        field="candidate repository root",
    )
    if Path(top_level).resolve(strict=False) != root:
        raise BuildContractError("candidate repository must be the Git worktree root")
    frontend_version = _frontend_version(commands, root)
    commit = _head(commands, root)
    _require_clean(commands, root)
    pyproject_bytes = _object_bytes(commands, root, commit, "pyproject.toml")
    lock_bytes = _object_bytes(commands, root, commit, "uv.lock")
    package_name, package_version, backend, backend_version = _project_contract(pyproject_bytes)

    # A second identity and cleanliness check closes the observation window
    # around the independently read Git objects.
    if _head(commands, root) != commit:
        raise BuildContractError("candidate HEAD changed during source inspection")
    _require_clean(commands, root)
    return SourceProvenance(
        repository=root,
        commit=commit,
        package_name=package_name,
        package_version=package_version,
        build_backend=backend,
        build_backend_version=backend_version,
        build_frontend_version=frontend_version,
        pyproject_sha256=_digest(pyproject_bytes),
        lock_sha256=_digest(lock_bytes),
        pyproject_bytes=pyproject_bytes,
        lock_bytes=lock_bytes,
    )


def recheck_candidate_source(
    source: SourceProvenance,
    *,
    commands: CommandService = _DEFAULT_COMMANDS,
) -> None:
    """Fail if the bound worktree, commit, cleanliness, or object bytes changed."""

    try:
        root = _real_repository(source.repository)
        if root != source.repository or _head(commands, root) != source.commit:
            raise BuildContractError("candidate source changed after inspection")
        _require_clean(commands, root)
        pyproject_bytes = _object_bytes(commands, root, source.commit, "pyproject.toml")
        lock_bytes = _object_bytes(commands, root, source.commit, "uv.lock")
        if (
            pyproject_bytes != source.pyproject_bytes
            or lock_bytes != source.lock_bytes
            or _digest(pyproject_bytes) != source.pyproject_sha256
            or _digest(lock_bytes) != source.lock_sha256
        ):
            raise BuildContractError("candidate committed inputs changed after inspection")
        _project_contract(pyproject_bytes)
    except BuildContractError as exc:
        raise BuildContractError(str(exc), failure_kind="provenance") from exc


def _request_paths(request: BuildRequest, source: SourceProvenance) -> tuple[Path, Path]:
    repository = _real_repository(request.repository)
    if repository != source.repository:
        raise BuildContractError("build request repository must match inspected source")
    workspace = request.workspace
    if not workspace.is_absolute() or ".." in workspace.parts:
        raise BuildContractError("candidate workspace must be an absolute path")
    workspace = workspace.resolve(strict=False)
    if workspace.exists() or workspace.is_symlink():
        raise BuildContractError("candidate workspace must be absent")
    if workspace.is_relative_to(repository):
        raise BuildContractError("candidate workspace must be outside the repository")
    parent = workspace.parent
    try:
        parent_metadata = parent.lstat()
        parent_resolved = parent.resolve(strict=True)
    except OSError as exc:
        raise BuildContractError(
            "candidate workspace parent must be an existing directory"
        ) from exc
    if (
        parent.is_symlink()
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_resolved != parent
    ):
        raise BuildContractError("candidate workspace parent must be a real directory")
    python = request.python_executable
    if not python.is_absolute():
        raise BuildContractError("candidate Python must be an absolute executable")
    try:
        python_metadata = python.lstat()
    except OSError as exc:
        raise BuildContractError("candidate Python must be an existing executable") from exc
    if (
        python.is_symlink()
        or not stat.S_ISREG(python_metadata.st_mode)
        or python_metadata.st_mode & 0o111 == 0
    ):
        raise BuildContractError("candidate Python must be a regular non-symlink executable")
    return workspace, python


def _create_workspace(workspace: Path) -> int:
    descriptor: int | None = None
    try:
        workspace.mkdir(mode=0o700)
        created = workspace.lstat()
        if workspace.is_symlink() or not stat.S_ISDIR(created.st_mode):
            raise BuildContractError("candidate workspace identity changed during creation")
        workspace.chmod(0o700, follow_symlinks=False)
        descriptor = os.open(
            workspace,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        opened = os.fstat(descriptor)
        current = workspace.lstat()
        resolved = workspace.resolve(strict=True)
        created_identity = (created.st_dev, created.st_ino)
        if (
            created_identity != (opened.st_dev, opened.st_ino)
            or created_identity != (current.st_dev, current.st_ino)
            or not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o700
            or stat.S_IMODE(current.st_mode) != 0o700
            or resolved != workspace
        ):
            raise BuildContractError("candidate workspace identity changed during creation")
        result = descriptor
        descriptor = None
        return result
    except FileExistsError as exc:
        raise BuildContractError("candidate workspace must remain absent until creation") from exc
    except OSError as exc:
        raise BuildContractError("candidate workspace could not be created safely") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _check_workspace(workspace: Path, directory_fd: int) -> None:
    try:
        path_metadata = workspace.lstat()
        held_metadata = os.fstat(directory_fd)
    except OSError as exc:
        raise BuildContractError("candidate workspace identity became unavailable") from exc
    if (
        workspace.is_symlink()
        or not stat.S_ISDIR(path_metadata.st_mode)
        or (path_metadata.st_dev, path_metadata.st_ino)
        != (held_metadata.st_dev, held_metadata.st_ino)
        or stat.S_IMODE(path_metadata.st_mode) != 0o700
    ):
        raise BuildContractError("candidate workspace identity changed")


def _new_directory(
    path: Path,
    *,
    failure_kind: BuildFailureKind = "build",
) -> None:
    try:
        path.mkdir(mode=0o700)
    except OSError as exc:
        raise BuildContractError(
            "candidate private directory could not be created",
            failure_kind=failure_kind,
        ) from exc


def _extract_archive(archive_bytes: bytes, destination: Path) -> None:
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
            archive.extractall(destination, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise BuildContractError("candidate Git archive could not be extracted safely") from exc


def _require_archived_inputs(source: SourceProvenance, snapshot: Path) -> None:
    for name, expected in (
        ("pyproject.toml", source.pyproject_bytes),
        ("uv.lock", source.lock_bytes),
    ):
        path = snapshot / name
        try:
            metadata = path.lstat()
            actual = path.read_bytes()
        except OSError as exc:
            raise BuildContractError(f"archived {name} is unavailable") from exc
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or actual != expected:
            raise BuildContractError(f"archived {name} does not match committed object bytes")


def _snapshot_regular_file(
    path: Path,
    *,
    kind: str,
    failure_kind: BuildFailureKind = "build",
) -> _RegularFileSnapshot:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise BuildContractError(
            f"{kind} must be a regular non-symlink file",
            failure_kind=failure_kind,
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BuildContractError(
                f"{kind} must be a regular non-symlink file",
                failure_kind=failure_kind,
            )
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        data = b"".join(chunks)
    finally:
        os.close(descriptor)
    return _RegularFileSnapshot(
        path=path,
        data=data,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size=metadata.st_size,
        mode=metadata.st_mode,
        mtime_ns=metadata.st_mtime_ns,
    )


def _require_unchanged_file(
    snapshot: _RegularFileSnapshot,
    *,
    kind: str,
    failure_kind: BuildFailureKind = "build",
) -> None:
    try:
        current = _snapshot_regular_file(
            snapshot.path,
            kind=kind,
            failure_kind=failure_kind,
        )
    except BuildContractError as exc:
        raise BuildContractError(
            f"{kind} changed before its consumer completed",
            failure_kind=failure_kind,
        ) from exc
    if (
        current.data != snapshot.data
        or current.device != snapshot.device
        or current.inode != snapshot.inode
        or current.size != snapshot.size
        or current.mode != snapshot.mode
        or current.mtime_ns != snapshot.mtime_ns
    ):
        raise BuildContractError(
            f"{kind} changed before its consumer completed",
            failure_kind=failure_kind,
        )


def _one_wheel(wheel_directory: Path) -> tuple[Path, _RegularFileSnapshot]:
    try:
        entries = tuple(wheel_directory.iterdir())
    except OSError as exc:
        raise BuildContractError("wheel directory is unavailable") from exc
    wheels = tuple(entry for entry in entries if entry.suffix == ".whl")
    other = tuple(entry for entry in entries if entry.suffix != ".whl")
    if len(wheels) != 1:
        raise BuildContractError("candidate build must produce exactly one regular wheel")
    if any(entry.name != ".gitignore" for entry in other) or len(other) > 1:
        raise BuildContractError("wheel directory contains an unexpected build output")
    if other:
        marker = other[0]
        try:
            marker_metadata = marker.lstat()
        except OSError as exc:
            raise BuildContractError("uv wheel-directory marker is unavailable") from exc
        if marker.is_symlink() or not stat.S_ISREG(marker_metadata.st_mode):
            raise BuildContractError("uv wheel-directory marker must be a regular file")
    wheel = wheels[0]
    try:
        metadata = wheel.lstat()
    except OSError as exc:
        raise BuildContractError("candidate wheel is unavailable") from exc
    if wheel.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise BuildContractError("candidate wheel must be a regular non-symlink file")
    return wheel, _snapshot_regular_file(wheel, kind="candidate wheel")


def _validate_wheel_metadata(
    wheel_bytes: bytes,
    *,
    package_name: str,
    package_version: str,
) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel:
            names = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise BuildContractError("candidate wheel must contain exactly one METADATA file")
            metadata = BytesParser().parsebytes(wheel.read(names[0]))
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise BuildContractError("candidate wheel metadata is unreadable") from exc
    if metadata.get("Name") != package_name or metadata.get("Version") != package_version:
        raise BuildContractError("candidate wheel metadata does not match inspected source")


def _require_executable_file(
    path: Path,
    *,
    kind: str,
    failure_kind: BuildFailureKind = "build",
) -> None:
    snapshot = _snapshot_regular_file(path, kind=kind, failure_kind=failure_kind)
    if snapshot.mode & 0o111 == 0:
        raise BuildContractError(f"{kind} must be executable", failure_kind=failure_kind)


def _require_venv_interpreter(
    path: Path,
    *,
    venv: Path,
    requested_python: Path,
    failure_kind: BuildFailureKind = "build",
) -> None:
    try:
        venv_metadata = venv.lstat()
        path_metadata = path.lstat()
        resolved = path.resolve(strict=True)
        resolved_metadata = resolved.stat()
    except OSError as exc:
        raise BuildContractError(
            "candidate Python is unavailable",
            failure_kind=failure_kind,
        ) from exc
    if venv.is_symlink() or not stat.S_ISDIR(venv_metadata.st_mode):
        raise BuildContractError(
            "candidate venv must be a real directory",
            failure_kind=failure_kind,
        )
    if not path.is_relative_to(venv) or path.parent != venv / "bin":
        raise BuildContractError(
            "candidate Python path escaped the candidate venv",
            failure_kind=failure_kind,
        )
    if not (stat.S_ISREG(path_metadata.st_mode) or stat.S_ISLNK(path_metadata.st_mode)):
        raise BuildContractError(
            "candidate Python must be a regular executable or symlink",
            failure_kind=failure_kind,
        )
    if not stat.S_ISREG(resolved_metadata.st_mode) or resolved_metadata.st_mode & 0o111 == 0:
        raise BuildContractError(
            "candidate Python must resolve to a regular executable",
            failure_kind=failure_kind,
        )
    if stat.S_ISLNK(path_metadata.st_mode) and resolved != requested_python:
        # uv's ordinary venv layout links `bin/python` to the exact interpreter
        # selected by --python.  No other external symlink target is trusted.
        raise BuildContractError(
            "candidate Python symlink escaped its bound interpreter",
            failure_kind=failure_kind,
        )
    if stat.S_ISREG(path_metadata.st_mode) and not resolved.is_relative_to(venv):
        raise BuildContractError(
            "candidate Python path escaped the candidate venv",
            failure_kind=failure_kind,
        )


def _import_proof_script() -> str:
    return (
        "import importlib,json,pkgutil;"
        "root=importlib.import_module('docmend');"
        "names=['docmend']+sorted(m.name for m in pkgutil.walk_packages("
        "root.__path__,'docmend.') if m.name.startswith('docmend.scale'));"
        "print(json.dumps({name:importlib.import_module(name).__file__ for name in names},"
        "sort_keys=True))"
    )


def _expected_scale_modules(snapshot: Path) -> frozenset[str]:
    package = snapshot / "src/docmend"
    try:
        modules = {
            f"docmend.{path.stem}"
            for path in package.glob("scale*.py")
            if path.is_file() and not path.is_symlink()
        }
    except OSError as exc:
        raise BuildContractError("candidate source modules are unavailable") from exc
    return frozenset({"docmend", *modules})


def _prove_import_origins(
    commands: CommandService,
    *,
    candidate_python: Path,
    cwd: Path,
    venv: Path,
    snapshot: Path,
    private_home: Path,
) -> None:
    output = _run(
        commands,
        (str(candidate_python), "-I", "-c", _import_proof_script()),
        cwd=cwd,
        kind="installed import proof",
        private_home=private_home,
        failure_kind="install",
    )
    try:
        document = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildContractError("installed import proof must return valid JSON") from exc
    if type(document) is not dict or any(
        type(name) is not str or type(origin) is not str
        for name, origin in cast("dict[object, object]", document).items()
    ):
        raise BuildContractError("installed import proof must map modules to origins")
    origins = cast("dict[str, str]", document)
    if not _expected_scale_modules(snapshot).issubset(origins):
        raise BuildContractError("installed import proof omitted a scale module")
    venv_root = venv.resolve(strict=True)
    for origin in origins.values():
        path = Path(origin)
        if not path.is_absolute() or not path.resolve(strict=False).is_relative_to(venv_root):
            raise BuildContractError("installed import origin escaped the candidate venv")


def prepare_candidate(
    request: BuildRequest,
    *,
    source: SourceProvenance,
    commands: CommandService = _DEFAULT_COMMANDS,
) -> CandidateBuild:
    """Archive, build, install, and prove one exact clean-HEAD candidate."""

    workspace, python = _request_paths(request, source)
    recheck_candidate_source(source, commands=commands)
    workspace_fd = _create_workspace(workspace)
    workspace_lease = CandidateWorkspaceLease(workspace, workspace_fd)
    workspace_lease.require_current_identity()
    wheel_sha256: str | None = None
    try:
        _check_workspace(workspace, workspace_fd)
        private_home = workspace / "private-home"
        _new_directory(private_home)
        for name in ("tmp", "cache", "config", "state"):
            _new_directory(private_home / name)
        snapshot = workspace / "source"
        _new_directory(snapshot)
        archive_bytes = _run(
            commands,
            ("git", "archive", "--format=tar", source.commit),
            cwd=source.repository,
            kind="candidate Git archive",
            private_home=private_home,
        )
        _extract_archive(archive_bytes, snapshot)
        _require_archived_inputs(source, snapshot)
        recheck_candidate_source(source, commands=commands)
        _check_workspace(workspace, workspace_fd)

        wheel_directory = workspace / "wheel"
        _new_directory(wheel_directory)
        _run(
            commands,
            (
                "uv",
                "--no-config",
                "build",
                "--wheel",
                "--no-sources",
                "--force-pep517",
                "--out-dir",
                str(wheel_directory),
                str(snapshot),
            ),
            cwd=workspace,
            kind="candidate wheel build",
            private_home=private_home,
        )
        recheck_candidate_source(source, commands=commands)
        wheel, wheel_snapshot = _one_wheel(wheel_directory)
        _validate_wheel_metadata(
            wheel_snapshot.data,
            package_name=source.package_name,
            package_version=source.package_version,
        )
        wheel_sha256 = _digest(wheel_snapshot.data)

        venv = workspace / "venv"
        _run(
            commands,
            (
                "uv",
                "--no-config",
                "venv",
                "--no-project",
                "--python",
                str(python),
                "--no-python-downloads",
                str(venv),
            ),
            cwd=workspace,
            kind="candidate venv creation",
            private_home=private_home,
            failure_kind="install",
        )
        candidate_python = venv / "bin/python"
        _require_venv_interpreter(
            candidate_python,
            venv=venv,
            requested_python=python,
            failure_kind="install",
        )
        candidate_python_snapshot = _snapshot_artifact_path(
            candidate_python,
            kind="candidate Python",
            allow_symlink=True,
            executable=True,
        )
        runtime = workspace / "runtime-requirements.txt"
        _run(
            commands,
            (
                "uv",
                "--no-config",
                "export",
                "--project",
                str(snapshot),
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--no-sources",
                "--format",
                "requirements.txt",
                "--output-file",
                str(runtime),
            ),
            cwd=workspace,
            kind="locked runtime export",
            private_home=private_home,
            failure_kind="install",
        )
        runtime_snapshot = _snapshot_regular_file(
            runtime,
            kind="locked runtime export",
            failure_kind="install",
        )
        executable = venv / "bin/docmend"
        with _sealed_input(
            runtime_snapshot.data,
            name="docmend-runtime-requirements",
        ) as (runtime_input, runtime_fd):
            _require_artifact_snapshot(
                candidate_python_snapshot,
                allow_symlink=True,
                executable=True,
            )
            _run(
                commands,
                (
                    "uv",
                    "--no-config",
                    "pip",
                    "install",
                    "--python",
                    str(candidate_python),
                    "--require-hashes",
                    "--no-deps",
                    "--only-binary",
                    ":all:",
                    "-r",
                    str(runtime_input),
                ),
                cwd=workspace,
                kind="hash-required runtime install",
                private_home=private_home,
                pass_fds=(runtime_fd,),
                failure_kind="install",
            )
            _require_artifact_snapshot(
                candidate_python_snapshot,
                allow_symlink=True,
                executable=True,
            )
        _require_unchanged_file(
            runtime_snapshot,
            kind="locked runtime export",
            failure_kind="install",
        )
        recheck_candidate_source(source, commands=commands)
        _require_unchanged_file(
            wheel_snapshot,
            kind="candidate wheel",
            failure_kind="install",
        )
        wheel_requirement = (
            f"{source.package_name} @ {wheel.as_uri()} --hash={_digest(wheel_snapshot.data)}\n"
        ).encode("ascii")
        with _sealed_input(
            wheel_requirement,
            name="docmend-wheel-requirement",
        ) as (wheel_input, wheel_fd):
            _require_artifact_snapshot(
                candidate_python_snapshot,
                allow_symlink=True,
                executable=True,
            )
            _run(
                commands,
                (
                    "uv",
                    "--no-config",
                    "pip",
                    "install",
                    "--python",
                    str(candidate_python),
                    "--require-hashes",
                    "--no-index",
                    "--no-deps",
                    "-r",
                    str(wheel_input),
                ),
                cwd=workspace,
                kind="candidate wheel install",
                private_home=private_home,
                pass_fds=(wheel_fd,),
                failure_kind="install",
            )
            _require_artifact_snapshot(
                candidate_python_snapshot,
                allow_symlink=True,
                executable=True,
            )
        _require_unchanged_file(
            wheel_snapshot,
            kind="candidate wheel",
            failure_kind="install",
        )
        _require_artifact_snapshot(
            candidate_python_snapshot,
            allow_symlink=True,
            executable=True,
        )
        _run(
            commands,
            (
                "uv",
                "--no-config",
                "pip",
                "check",
                "--python",
                str(candidate_python),
            ),
            cwd=workspace,
            kind="candidate pip check",
            private_home=private_home,
            failure_kind="install",
        )
        _require_artifact_snapshot(
            candidate_python_snapshot,
            allow_symlink=True,
            executable=True,
        )
        recheck_candidate_source(source, commands=commands)
        _require_venv_interpreter(
            candidate_python,
            venv=venv,
            requested_python=python,
            failure_kind="install",
        )
        try:
            _require_executable_file(
                executable,
                kind="candidate executable",
                failure_kind="install",
            )
            proof_cwd = workspace / "import-proof"
            _new_directory(proof_cwd, failure_kind="install")
            artifact_lease = CandidateArtifactLease(
                executable=_snapshot_artifact_path(
                    executable,
                    kind="candidate executable",
                    allow_symlink=False,
                    executable=True,
                ),
                venv_python=candidate_python_snapshot,
                measurement_wrapper=_snapshot_artifact_path(
                    snapshot / "scripts/measure_scale_stage.py",
                    kind="candidate measurement wrapper",
                    allow_symlink=False,
                    executable=False,
                ),
            )
            artifact_lease.require_current_identity()
            _prove_import_origins(
                commands,
                candidate_python=candidate_python,
                cwd=proof_cwd,
                venv=venv,
                snapshot=snapshot,
                private_home=private_home,
            )
            artifact_lease.require_current_identity()
        except BuildContractError as exc:
            if exc.failure_kind == "provenance":
                raise
            raise BuildContractError(str(exc), failure_kind="install") from exc
        recheck_candidate_source(source, commands=commands)
        _check_workspace(workspace, workspace_fd)
        workspace_lease.require_current_identity()
        artifact_lease.require_current_identity()
    except BuildContractError as exc:
        exc.with_checkpoint(
            wheel_sha256=wheel_sha256,
            workspace_lease=workspace_lease,
        )
        raise

    assert wheel_sha256 is not None

    return CandidateBuild(
        commit=source.commit,
        package_name=source.package_name,
        package_version=source.package_version,
        build_backend_version=source.build_backend_version,
        build_frontend_version=source.build_frontend_version,
        source_snapshot=snapshot,
        wheel=wheel,
        wheel_sha256=wheel_sha256,
        venv=venv,
        venv_python=candidate_python,
        executable=executable,
        workspace_lease=workspace_lease,
        artifact_lease=artifact_lease,
    )
