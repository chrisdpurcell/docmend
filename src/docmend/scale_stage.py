"""Run one private child stage for an external NFR-001 RSS measurement.

The request, result, argv, working directory, environment, and captured output
are private qualification-harness data. This module never constructs public
``StageEvidence``; a later orchestrator may reduce a trustworthy private result
to aggregate evidence without copying paths, argv, environment, or output.

Linux is load-bearing: ``RUSAGE_CHILDREN.ru_maxrss`` is measured in KiB, and
child swap telemetry comes from ``/proc/<pid>/status``. A fresh supervisor owns
exactly one child so the cumulative child-usage counter identifies that child.
"""

import ctypes
import errno
import json
import math
import os
import re
import resource
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import IO, Literal, Protocol, cast

REQUEST_SCHEMA = "docmend/scale-stage-request"
RESULT_SCHEMA = "docmend/scale-stage-result"
STAGE_SCHEMA_VERSION = "1.0"
POLL_INTERVAL_SECONDS = 0.05

_AT_EMPTY_PATH = 0x1000
_AT_FDCWD = -100
_AT_SYMLINK_FOLLOW = 0x400
_DIRECT_LINK_FALLBACK_ERRNOS = frozenset(
    {errno.EINVAL, errno.ENOENT, errno.ENOSYS, errno.EOPNOTSUPP, errno.EPERM}
)
_O_TMPFILE_FLAG = cast("int", getattr(os, "O_TMPFILE", 0))
_LIBC = ctypes.CDLL(None, use_errno=True)
_LINKAT = cast("Callable[..., int] | None", getattr(_LIBC, "linkat", None))

type StageName = Literal["scan", "plan", "apply", "verify"]
type StageErrorCode = Literal["spawn-failed", "reap-failed"]

STAGE_NAMES: tuple[StageName, ...] = ("scan", "plan", "apply", "verify")
INHERITED_ENVIRONMENT_KEYS: tuple[str, ...] = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "TEMP",
    "TMP",
    "TMPDIR",
    "TZ",
)
STRIPPED_PYTHON_ENVIRONMENT_KEYS: tuple[str, ...] = (
    "PYTHONTRACEMALLOC",
    "PYTHONPATH",
    "PYTHONHOME",
)

# The request overlay is private but still cannot turn the binding child into an
# instrumented process, inject code at loader startup, or carry credentials.
# PYTHONPATH/PYTHONHOME remain accepted inputs only so the final-environment
# strip is testable and fail-closed; they never reach the child.
_ALLOWED_STRIPPED_PYTHON_KEYS = frozenset({"PYTHONPATH", "PYTHONHOME", "PYTHONNOUSERSITE"})
_BLOCKED_EXACT_ENVIRONMENT_KEYS = frozenset(
    {
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "SSH_AUTH_SOCK",
        "VAULT_TOKEN",
        "BAO_TOKEN",
    }
)
_BLOCKED_ENVIRONMENT_PREFIXES = (
    "ASAN_",
    "CPUPROFILE",
    "COVERAGE_",
    "DD_",
    "DYLD_",
    "GCOV_",
    "HEAPPROFILE",
    "LD_",
    "LLVM_PROFILE_",
    "LSAN_",
    "MALLOC_",
    "MSAN_",
    "NEW_RELIC_",
    "OTEL_",
    "PYTEST_",
    "TSAN_",
    "UBSAN_",
)
_CREDENTIAL_ENVIRONMENT_MARKERS = ("CREDENTIAL", "PASSWORD", "SECRET", "TOKEN")
_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VM_SWAP = re.compile(r"^VmSwap:[ \t]+([0-9]+)[ \t]+kB$")
_PYTHON_EXECUTABLE = re.compile(r"^python(?:[0-9]+(?:\.[0-9]+)*)?[a-z]*?(?:\.exe)?$")

_REQUEST_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "stage",
        "argv",
        "cwd",
        "environment",
        "stdout",
        "stderr",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "stage",
        "completed",
        "exit_code",
        "elapsed_seconds",
        "peak_rss_bytes",
        "vm_swap_peak_bytes",
        "tracing_enabled",
        "stdout",
        "stderr",
        "error_code",
    }
)


class StageContractError(Exception):
    """A private request, path, file, or result violates the supervisor contract."""


class StageSupervisorError(Exception):
    """The supervisor could not produce or publish a trustworthy private result."""


class ChildProcess(Protocol):
    """The Popen slice needed by the one-child polling loop."""

    pid: int

    def poll(self) -> int | None: ...

    def wait(self) -> int: ...

    def kill(self) -> None: ...


class PopenFactory(Protocol):
    """Typed injection boundary for the one permitted child launch."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        shell: bool,
        stdin: int,
        close_fds: bool,
        cwd: Path,
        stdout: IO[bytes],
        stderr: IO[bytes],
        env: Mapping[str, str],
    ) -> ChildProcess: ...


type Clock = Callable[[], float]
type Sleeper = Callable[[float], None]
type StatusReader = Callable[[int], str]
type RusageReader = Callable[[], int]


def _require_unicode_scalar(value: str, *, field: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise StageContractError(f"{field} must contain only Unicode scalar values")


def _contract_mapping(document: object, fields: frozenset[str], *, kind: str) -> dict[str, object]:
    if type(document) is not dict:
        raise StageContractError(f"{kind} must be a JSON object")
    values = cast("dict[object, object]", document)
    if any(type(key) is not str for key in values):
        raise StageContractError(f"{kind} field names must be strings")
    typed = cast("dict[str, object]", values)
    if frozenset(typed) != fields:
        raise StageContractError(f"{kind} must contain exactly the versioned contract fields")
    return typed


def _stage_name(value: object) -> StageName:
    if type(value) is not str or value not in STAGE_NAMES:
        raise StageContractError("stage must name scan, plan, apply, or verify")
    return value


def _safe_output_name(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise StageContractError(f"{field} must be a non-empty relative output name")
    _require_unicode_scalar(value, field=field)
    name = PurePosixPath(value)
    if (
        name.is_absolute()
        or len(name.parts) != 1
        or name.as_posix() != value
        or value in {".", ".."}
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise StageContractError(f"{field} must be a safe workspace-relative output name")
    return value


def _absolute_cwd(value: object) -> Path:
    if type(value) is not str or not value or "\x00" in value:
        raise StageContractError("cwd must be a non-empty absolute path")
    _require_unicode_scalar(value, field="cwd")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise StageContractError("cwd must be a canonical absolute path")
    return path


def _argv(value: object) -> tuple[str, ...]:
    if type(value) is not list or not value:
        raise StageContractError("argv must be a non-empty JSON array")
    raw = cast("list[object]", value)
    if any(type(argument) is not str or "\x00" in argument for argument in raw):
        raise StageContractError("argv entries must be NUL-free strings")
    argv = tuple(cast("list[str]", raw))
    if not argv[0]:
        raise StageContractError("argv[0] must not be empty")
    for argument in argv:
        _require_unicode_scalar(argument, field="argv")
    _reject_environment_launcher(argv)
    _reject_python_tracemalloc(argv)
    return argv


def _reject_environment_launcher(argv: Sequence[str]) -> None:
    if Path(argv[0]).name.casefold() in {"env", "env.exe"}:
        raise StageContractError(
            "binding argv must not use an environment launcher that can bypass the fixed child environment"
        )


def _reject_python_tracemalloc(argv: Sequence[str]) -> None:
    if _PYTHON_EXECUTABLE.fullmatch(Path(argv[0]).name.casefold()) is None:
        return
    index = 1
    while index < len(argv):
        argument = argv[index]
        if argument in {"--", "-", "-c", "-m"} or not argument.startswith("-"):
            return
        if argument in {"-W", "--check-hash-based-pycs"}:
            index += 2
            continue
        if argument == "-X":
            if index + 1 < len(argv):
                option = argv[index + 1]
                if option == "tracemalloc" or option.startswith("tracemalloc="):
                    raise StageContractError("binding argv must not enable Python tracemalloc")
            index += 2
            continue
        if argument == "-Xtracemalloc" or argument.startswith("-Xtracemalloc="):
            raise StageContractError("binding argv must not enable Python tracemalloc")
        index += 1


def _environment(value: object) -> Mapping[str, str]:
    if type(value) is not dict:
        raise StageContractError("environment must be a JSON object")
    raw = cast("dict[object, object]", value)
    environment: dict[str, str] = {}
    for key_value, item_value in raw.items():
        if type(key_value) is not str or type(item_value) is not str:
            raise StageContractError("environment names and values must be strings")
        key = key_value
        item = item_value
        _require_unicode_scalar(key, field="environment name")
        _require_unicode_scalar(item, field="environment value")
        if _ENVIRONMENT_NAME.fullmatch(key) is None or "\x00" in item:
            raise StageContractError("environment contains an invalid name or NUL value")
        upper = key.upper()
        if key == "PYTHONTRACEMALLOC":
            raise StageContractError("environment must not explicitly enable tracemalloc")
        if key.startswith("PYTHON") and key not in _ALLOWED_STRIPPED_PYTHON_KEYS:
            raise StageContractError("environment must not configure Python instrumentation")
        if (
            key in _BLOCKED_EXACT_ENVIRONMENT_KEYS
            or upper.startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
            or any(marker in upper for marker in _CREDENTIAL_ENVIRONMENT_MARKERS)
        ):
            raise StageContractError("environment must not carry credentials or instrumentation")
        environment[key] = item
    return MappingProxyType(environment)


@dataclass(frozen=True, slots=True)
class StageRequest:
    """Validated private instructions for one fixed child process."""

    stage: StageName
    argv: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str]
    stdout: str
    stderr: str

    def __post_init__(self) -> None:
        if self.stage not in STAGE_NAMES:
            raise StageContractError("stage must name scan, plan, apply, or verify")
        if type(self.argv) is not tuple or not self.argv:
            raise StageContractError("argv must be a non-empty tuple")
        if any(type(argument) is not str or "\x00" in argument for argument in self.argv):
            raise StageContractError("argv entries must be NUL-free strings")
        if not self.argv[0]:
            raise StageContractError("argv[0] must not be empty")
        for argument in self.argv:
            _require_unicode_scalar(argument, field="argv")
        _reject_environment_launcher(self.argv)
        _reject_python_tracemalloc(self.argv)
        if not self.cwd.is_absolute() or ".." in self.cwd.parts:
            raise StageContractError("cwd must be a canonical absolute path")
        _require_unicode_scalar(self.cwd.as_posix(), field="cwd")
        environment = _environment(dict(self.environment))
        object.__setattr__(self, "environment", environment)
        stdout = _safe_output_name(self.stdout, field="stdout")
        stderr = _safe_output_name(self.stderr, field="stderr")
        if stdout == stderr:
            raise StageContractError("stdout and stderr names must not collide")

    @classmethod
    def from_document(cls, document: object) -> StageRequest:
        """Validate and return one exact versioned request document."""
        values = _contract_mapping(document, _REQUEST_FIELDS, kind="stage request")
        if values["schema"] != REQUEST_SCHEMA or values["schema_version"] != STAGE_SCHEMA_VERSION:
            raise StageContractError("stage request schema or version is unsupported")
        return cls(
            stage=_stage_name(values["stage"]),
            argv=_argv(values["argv"]),
            cwd=_absolute_cwd(values["cwd"]),
            environment=_environment(values["environment"]),
            stdout=_safe_output_name(values["stdout"], field="stdout"),
            stderr=_safe_output_name(values["stderr"], field="stderr"),
        )

    def to_document(self) -> dict[str, object]:
        """Return the exact private JSON representation."""
        return {
            "schema": REQUEST_SCHEMA,
            "schema_version": STAGE_SCHEMA_VERSION,
            "stage": self.stage,
            "argv": list(self.argv),
            "cwd": self.cwd.as_posix(),
            "environment": dict(self.environment),
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _strict_int_or_none(value: object, *, field: str, non_negative: bool) -> int | None:
    if value is None:
        return None
    if type(value) is not int or (non_negative and value < 0):
        qualifier = "non-negative " if non_negative else ""
        raise StageContractError(f"{field} must be a {qualifier}integer or null")
    return value


def _finite_elapsed(value: object) -> float:
    if type(value) not in {int, float}:
        raise StageContractError("elapsed_seconds must be a finite non-negative number")
    seconds = float(cast("int | float", value))
    if not math.isfinite(seconds) or seconds < 0:
        raise StageContractError("elapsed_seconds must be a finite non-negative number")
    return seconds


@dataclass(frozen=True, slots=True)
class StageResult:
    """Private measurement result; paths, argv, and output never become evidence."""

    stage: StageName
    completed: bool
    exit_code: int | None
    elapsed_seconds: float
    peak_rss_bytes: int | None
    vm_swap_peak_bytes: int | None
    tracing_enabled: Literal[False]
    stdout: str
    stderr: str
    error_code: StageErrorCode | None

    def __post_init__(self) -> None:
        if self.stage not in STAGE_NAMES:
            raise StageContractError("stage must name scan, plan, apply, or verify")
        if type(self.completed) is not bool or self.tracing_enabled is not False:
            raise StageContractError("result booleans must be strict and tracing must be disabled")
        exit_code = _strict_int_or_none(self.exit_code, field="exit_code", non_negative=False)
        peak_rss = _strict_int_or_none(
            self.peak_rss_bytes, field="peak_rss_bytes", non_negative=True
        )
        vm_swap = _strict_int_or_none(
            self.vm_swap_peak_bytes, field="vm_swap_peak_bytes", non_negative=True
        )
        elapsed = _finite_elapsed(self.elapsed_seconds)
        object.__setattr__(self, "exit_code", exit_code)
        object.__setattr__(self, "peak_rss_bytes", peak_rss)
        object.__setattr__(self, "vm_swap_peak_bytes", vm_swap)
        object.__setattr__(self, "elapsed_seconds", elapsed)
        stdout = _safe_output_name(self.stdout, field="stdout")
        stderr = _safe_output_name(self.stderr, field="stderr")
        if stdout == stderr:
            raise StageContractError("stdout and stderr names must not collide")
        if self.error_code not in (None, "spawn-failed", "reap-failed"):
            raise StageContractError("error_code is not a finite supervisor error")
        if self.completed:
            if exit_code is None or peak_rss is None or self.error_code is not None:
                raise StageContractError("completed result requires exit/RSS and no error")
        elif (
            exit_code is not None
            or peak_rss is not None
            or vm_swap is not None
            or self.error_code is None
        ):
            raise StageContractError("incomplete result must be a spawn/reap failure")

    @classmethod
    def from_document(cls, document: object) -> StageResult:
        """Validate and return one exact versioned result document."""
        values = _contract_mapping(document, _RESULT_FIELDS, kind="stage result")
        if values["schema"] != RESULT_SCHEMA or values["schema_version"] != STAGE_SCHEMA_VERSION:
            raise StageContractError("stage result schema or version is unsupported")
        if type(values["completed"]) is not bool or values["tracing_enabled"] is not False:
            raise StageContractError("result booleans must be strict and tracing must be disabled")
        error_value = values["error_code"]
        if error_value not in (None, "spawn-failed", "reap-failed"):
            raise StageContractError("error_code is not a finite supervisor error")
        return cls(
            stage=_stage_name(values["stage"]),
            completed=values["completed"],
            exit_code=_strict_int_or_none(
                values["exit_code"], field="exit_code", non_negative=False
            ),
            elapsed_seconds=_finite_elapsed(values["elapsed_seconds"]),
            peak_rss_bytes=_strict_int_or_none(
                values["peak_rss_bytes"], field="peak_rss_bytes", non_negative=True
            ),
            vm_swap_peak_bytes=_strict_int_or_none(
                values["vm_swap_peak_bytes"], field="vm_swap_peak_bytes", non_negative=True
            ),
            tracing_enabled=False,
            stdout=_safe_output_name(values["stdout"], field="stdout"),
            stderr=_safe_output_name(values["stderr"], field="stderr"),
            error_code=error_value,
        )

    def to_document(self) -> dict[str, object]:
        """Return the exact private JSON representation."""
        return {
            "schema": RESULT_SCHEMA,
            "schema_version": STAGE_SCHEMA_VERSION,
            "stage": self.stage,
            "completed": self.completed,
            "exit_code": self.exit_code,
            "elapsed_seconds": self.elapsed_seconds,
            "peak_rss_bytes": self.peak_rss_bytes,
            "vm_swap_peak_bytes": self.vm_swap_peak_bytes,
            "tracing_enabled": self.tracing_enabled,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_code": self.error_code,
        }


def _json_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise StageContractError("JSON contains a duplicate object key")
        document[key] = value
    return document


def _reject_json_constant(_value: str) -> object:
    raise StageContractError("JSON numbers must be finite")


def _read_request_fd(fd: int) -> StageRequest:
    stats = os.fstat(fd)
    if not stat.S_ISREG(stats.st_mode) or stat.S_IMODE(stats.st_mode) != 0o600:
        raise StageContractError("request must be a regular no-follow file with mode 0600")
    try:
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as request_file:
            raw = request_file.read()
    except (OSError, UnicodeError) as exc:
        raise StageContractError("request is not readable strict UTF-8 JSON") from exc
    try:
        document = cast(
            "object",
            json.loads(
                raw,
                object_pairs_hook=_json_object_pairs,
                parse_constant=_reject_json_constant,
            ),
        )
    except (RecursionError, ValueError) as exc:
        raise StageContractError("request is not valid strict JSON") from exc
    return StageRequest.from_document(document)


def load_stage_request(path: Path) -> StageRequest:
    """Open one owner-only regular request without following its final name."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise StageContractError("request must be a regular no-follow file with mode 0600") from exc
    try:
        return _read_request_fd(fd)
    finally:
        os.close(fd)


def _absolute_lexical(path: Path) -> Path:
    # resolve() would follow the final workspace symlink before the no-follow
    # check could reject it; abspath normalizes only lexical dot components.
    return Path(os.path.abspath(path))  # noqa: PTH100


def _open_private_workspace(workspace: Path) -> int:
    try:
        lexical_stats = os.lstat(workspace)
        resolved = workspace.resolve(strict=True)
    except OSError as exc:
        raise StageContractError("private workspace must already exist") from exc
    if stat.S_ISLNK(lexical_stats.st_mode) or resolved != workspace:
        raise StageContractError("private workspace must be a real directory, not a symlink")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(workspace, flags)
    except OSError as exc:
        raise StageContractError(
            "private workspace must be a real directory, not a symlink"
        ) from exc
    try:
        stats = os.fstat(fd)
        current_stats = os.lstat(workspace)
        current_resolved = workspace.resolve(strict=True)
    except OSError as exc:
        os.close(fd)
        raise StageContractError("private workspace identity changed during validation") from exc
    lexical_identity = (lexical_stats.st_dev, lexical_stats.st_ino)
    descriptor_identity = (stats.st_dev, stats.st_ino)
    current_identity = (current_stats.st_dev, current_stats.st_ino)
    if (
        lexical_identity != descriptor_identity
        or current_identity != descriptor_identity
        or stat.S_ISLNK(current_stats.st_mode)
        or current_resolved != workspace
    ):
        os.close(fd)
        raise StageContractError("private workspace identity changed during validation")
    if not stat.S_ISDIR(stats.st_mode) or stat.S_IMODE(stats.st_mode) != 0o700:
        os.close(fd)
        raise StageContractError("private workspace must have exact mode 0700")
    return fd


def _validate_cwd(cwd: Path) -> None:
    try:
        stats = os.lstat(cwd)
        resolved = cwd.resolve(strict=True)
    except OSError as exc:
        raise StageContractError("cwd must be an existing real non-symlink directory") from exc
    if not stat.S_ISDIR(stats.st_mode) or stat.S_ISLNK(stats.st_mode) or resolved != cwd:
        raise StageContractError("cwd must be an existing real non-symlink directory")


def _name_exists(workspace_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=workspace_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise StageContractError("private output name cannot be inspected safely") from exc
    return True


def _create_private_output(workspace_fd: int, name: str) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(name, flags, 0o600, dir_fd=workspace_fd)
    except FileExistsError as exc:
        raise StageContractError("private output already exists or collides") from exc
    except OSError as exc:
        raise StageContractError("private output cannot be created safely") from exc
    try:
        os.fchmod(fd, 0o600)
        stats = os.fstat(fd)
        if not stat.S_ISREG(stats.st_mode) or stat.S_IMODE(stats.st_mode) != 0o600:
            raise StageContractError("private output must be a regular mode-0600 file")
    except OSError, StageContractError:
        # The name may have been substituted after the exclusive open. Closing
        # the descriptor is safe; pathname cleanup could delete an unknown file.
        os.close(fd)
        raise
    return fd


def _binding_environment(overlay: Mapping[str, str]) -> dict[str, str]:
    # Only this finite process-neutral subset crosses from the supervisor.
    # In particular, credentials and profiler/import-hook variables inherited
    # by the wrapper are absent unless the validated private request supplies a
    # non-blocked key explicitly.
    environment = {key: os.environ[key] for key in INHERITED_ENVIRONMENT_KEYS if key in os.environ}
    environment.update(overlay)
    for key in STRIPPED_PYTHON_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _default_popen(
    argv: Sequence[str],
    *,
    shell: bool,
    stdin: int,
    close_fds: bool,
    cwd: Path,
    stdout: IO[bytes],
    stderr: IO[bytes],
    env: Mapping[str, str],
) -> ChildProcess:
    return subprocess.Popen(
        argv,
        shell=shell,
        stdin=stdin,
        close_fds=close_fds,
        cwd=cwd,
        stdout=stdout,
        stderr=stderr,
        env=env,
    )


def _read_child_status(pid: int) -> str:
    return Path(f"/proc/{pid}/status").read_text(encoding="ascii")


def _child_rusage_kib() -> int:
    value = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if type(value) is not int:
        raise StageSupervisorError("RUSAGE_CHILDREN returned an invalid Linux RSS")
    return value


def _parse_vm_swap(status_text: str) -> int:
    fields = [line for line in status_text.splitlines() if line.startswith("VmSwap:")]
    if len(fields) != 1:
        raise StageContractError("child VmSwap telemetry is unavailable")
    match = _VM_SWAP.fullmatch(fields[0])
    if match is None:
        raise StageContractError("child VmSwap telemetry is unavailable")
    return int(match.group(1), 10) * 1024


def _clock_value(clock: Clock) -> float:
    value = clock()
    if type(value) not in {int, float}:
        raise StageSupervisorError("monotonic clock returned an invalid value")
    result = float(value)
    if not math.isfinite(result):
        raise StageSupervisorError("monotonic clock returned an invalid value")
    return result


def _elapsed(started: float, ended: float) -> float:
    elapsed = ended - started
    if not math.isfinite(elapsed) or elapsed < 0:
        raise StageSupervisorError("monotonic clock moved backwards")
    return elapsed


def _incomplete_result(
    request: StageRequest, *, elapsed_seconds: float, error_code: StageErrorCode
) -> StageResult:
    return StageResult(
        stage=request.stage,
        completed=False,
        exit_code=None,
        elapsed_seconds=elapsed_seconds,
        peak_rss_bytes=None,
        vm_swap_peak_bytes=None,
        tracing_enabled=False,
        stdout=request.stdout,
        stderr=request.stderr,
        error_code=error_code,
    )


def _run_stage_at(
    request: StageRequest,
    *,
    workspace_fd: int,
    popen: PopenFactory = _default_popen,
    clock: Clock = time.monotonic,
    sleep: Sleeper = time.sleep,
    status_reader: StatusReader = _read_child_status,
    getrusage: RusageReader = _child_rusage_kib,
) -> StageResult:
    """Launch one child using an already-validated private workspace descriptor.

    Unreadable or malformed child-swap telemetry degrades only that field to
    ``None``. A launched child is always finalized with one explicit ``wait``;
    ``Popen`` is deliberately not a context manager because its implicit wait
    would make the one-reap contract unprovable.
    """
    stdout_fd: int | None = None
    stderr_fd: int | None = None
    try:
        _validate_cwd(request.cwd)
        stdout_fd = _create_private_output(workspace_fd, request.stdout)
        try:
            stderr_fd = _create_private_output(workspace_fd, request.stderr)
        except StageContractError:
            # Preserve the owner-only stdout name on setup failure: after its
            # descriptor closes, the pathname cannot be unlinked by identity.
            os.close(stdout_fd)
            stdout_fd = None
            raise
        output_files = ExitStack()
        try:
            stdout_file = output_files.enter_context(cast("IO[bytes]", os.fdopen(stdout_fd, "wb")))
            stdout_fd = None
            stderr_file = output_files.enter_context(cast("IO[bytes]", os.fdopen(stderr_fd, "wb")))
            stderr_fd = None
            started = _clock_value(clock)
            try:
                process = popen(
                    request.argv,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                    cwd=request.cwd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=_binding_environment(request.environment),
                )
            except OSError:
                ended = _clock_value(clock)
                return _incomplete_result(
                    request,
                    elapsed_seconds=_elapsed(started, ended),
                    error_code="spawn-failed",
                )

            swap_available = True
            swap_samples = 0
            swap_peak = 0

            def sample_swap() -> None:
                nonlocal swap_available, swap_peak, swap_samples
                if not swap_available:
                    return
                try:
                    sample = _parse_vm_swap(status_reader(process.pid))
                except OSError, UnicodeError, StageContractError:
                    swap_available = False
                    return
                swap_samples += 1
                swap_peak = max(swap_peak, sample)

            try:
                sample_swap()
                while True:
                    if process.poll() is not None:
                        break
                    sleep(POLL_INTERVAL_SECONDS)
                    sample_swap()
            except Exception:
                # Sampling is deliberately best effort, but every launched
                # child must still reach the one explicit wait below. Letting
                # an injected reader/clock boundary escape here would orphan
                # the binding stage and invalidate the fresh-child RSS model.
                swap_available = False

            try:
                exit_code = process.wait()
            except OSError:
                # A second wait would violate the one-reap contract and could
                # itself block after an indeterminate first wait. Best-effort
                # SIGKILL prevents a still-live child. In the production CLI,
                # the fresh supervisor exits after publishing this explicit
                # incomplete result, so any unreaped child is then reparented.
                with suppress(OSError):
                    process.kill()
                ended = _clock_value(clock)
                return _incomplete_result(
                    request,
                    elapsed_seconds=_elapsed(started, ended),
                    error_code="reap-failed",
                )
            ended = _clock_value(clock)
            elapsed_seconds = _elapsed(started, ended)
            if type(exit_code) is not int:
                raise StageSupervisorError("child wait returned an invalid exit code")
            rss_kib = getrusage()
            if type(rss_kib) is not int or rss_kib < 0:
                raise StageSupervisorError("RUSAGE_CHILDREN returned an invalid Linux RSS")
            return StageResult(
                stage=request.stage,
                completed=True,
                exit_code=exit_code,
                elapsed_seconds=elapsed_seconds,
                peak_rss_bytes=rss_kib * 1024,
                vm_swap_peak_bytes=(swap_peak if swap_available and swap_samples > 0 else None),
                tracing_enabled=False,
                stdout=request.stdout,
                stderr=request.stderr,
                error_code=None,
            )
        finally:
            output_files.close()
    finally:
        if stdout_fd is not None:
            os.close(stdout_fd)
        if stderr_fd is not None:
            os.close(stderr_fd)


def run_stage(
    request: StageRequest,
    *,
    workspace: Path,
    popen: PopenFactory = _default_popen,
    clock: Clock = time.monotonic,
    sleep: Sleeper = time.sleep,
    status_reader: StatusReader = _read_child_status,
    getrusage: RusageReader = _child_rusage_kib,
) -> StageResult:
    """Launch, sample, and reap exactly one child, returning private measurements."""
    workspace = _absolute_lexical(workspace)
    workspace_fd = _open_private_workspace(workspace)
    try:
        return _run_stage_at(
            request,
            workspace_fd=workspace_fd,
            popen=popen,
            clock=clock,
            sleep=sleep,
            status_reader=status_reader,
            getrusage=getrusage,
        )
    finally:
        os.close(workspace_fd)


def _load_request_at(workspace_fd: int, name: str) -> StageRequest:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    try:
        fd = os.open(name, flags, dir_fd=workspace_fd)
    except OSError as exc:
        raise StageContractError("request must be a regular no-follow file with mode 0600") from exc
    try:
        return _read_request_fd(fd)
    finally:
        os.close(fd)


def _workspace_identity(workspace_fd: int) -> tuple[int, int]:
    stats = os.fstat(workspace_fd)
    return stats.st_dev, stats.st_ino


def _require_workspace_identity(
    workspace: Path, workspace_fd: int, expected: tuple[int, int]
) -> None:
    """Refuse publication if the validated workspace name changed identity."""
    descriptor_stats = os.fstat(workspace_fd)
    try:
        path_stats = os.lstat(workspace)
        resolved = workspace.resolve(strict=True)
    except OSError as exc:
        raise StageSupervisorError("private workspace identity changed during supervision") from exc
    current = (descriptor_stats.st_dev, descriptor_stats.st_ino)
    path_identity = (path_stats.st_dev, path_stats.st_ino)
    if (
        current != expected
        or path_identity != expected
        or stat.S_ISLNK(path_stats.st_mode)
        or resolved != workspace
        or stat.S_IMODE(descriptor_stats.st_mode) != 0o700
        or stat.S_IMODE(path_stats.st_mode) != 0o700
    ):
        raise StageSupervisorError("private workspace identity changed during supervision")


def _call_linkat(
    source_fd: int,
    source: bytes,
    workspace_fd: int,
    destination: bytes,
    flags: int,
) -> None:
    if _LINKAT is None:
        raise OSError(errno.ENOSYS, "linkat is required for private result publication")
    ctypes.set_errno(0)
    result = _LINKAT(
        ctypes.c_int(source_fd),
        ctypes.c_char_p(source),
        ctypes.c_int(workspace_fd),
        ctypes.c_char_p(destination),
        ctypes.c_int(flags),
    )
    if result != 0:
        error_number = ctypes.get_errno() or errno.EIO
        if error_number == errno.EEXIST:
            raise FileExistsError(error_number, os.strerror(error_number), os.fsdecode(destination))
        raise OSError(error_number, os.strerror(error_number), os.fsdecode(destination))


def _link_anonymous_file(source_fd: int, workspace_fd: int, name: str) -> None:
    destination = os.fsencode(name)
    try:
        _call_linkat(source_fd, b"", workspace_fd, destination, _AT_EMPTY_PATH)
        return
    except OSError as exc:
        if exc.errno not in _DIRECT_LINK_FALLBACK_ERRNOS:
            raise
    # open(2) documents this procfs form for unprivileged callers that cannot
    # use AT_EMPTY_PATH. The result is still reconciled to the held inode below.
    source = f"/proc/self/fd/{source_fd}".encode("ascii")
    _call_linkat(_AT_FDCWD, source, workspace_fd, destination, _AT_SYMLINK_FOLLOW)


def _publish_private_result(workspace_fd: int, name: str, result: StageResult) -> None:
    if _O_TMPFILE_FLAG == 0:
        raise StageSupervisorError("Linux O_TMPFILE is required for private result staging")
    try:
        staging_fd = os.open(
            ".",
            os.O_WRONLY | _O_TMPFILE_FLAG | os.O_CLOEXEC,
            0o600,
            dir_fd=workspace_fd,
        )
    except OSError as exc:
        raise StageSupervisorError("private anonymous result staging failed") from exc
    try:
        os.fchmod(staging_fd, 0o600)
        result_file = os.fdopen(staging_fd, "w", encoding="utf-8", closefd=False)
        with result_file:
            json.dump(result.to_document(), result_file, ensure_ascii=False, sort_keys=True)
            result_file.write("\n")
            result_file.flush()
            os.fsync(result_file.fileno())
        staged_stats = os.fstat(staging_fd)
        if not stat.S_ISREG(staged_stats.st_mode) or stat.S_IMODE(staged_stats.st_mode) != 0o600:
            raise StageSupervisorError("private result staging identity is invalid")
        try:
            _link_anonymous_file(staging_fd, workspace_fd, name)
        except FileExistsError as exc:
            raise StageSupervisorError("private result publication collision") from exc
        except OSError as exc:
            raise StageSupervisorError("private result publication failed") from exc
        try:
            published_stats = os.stat(name, dir_fd=workspace_fd, follow_symlinks=False)
        except OSError as exc:
            raise StageSupervisorError("private result publication cannot be verified") from exc
        if (
            (published_stats.st_dev, published_stats.st_ino)
            != (staged_stats.st_dev, staged_stats.st_ino)
            or not stat.S_ISREG(published_stats.st_mode)
            or stat.S_IMODE(published_stats.st_mode) != 0o600
        ):
            raise StageSupervisorError("private result publication identity is invalid")
        # Anonymous staging removes the pathname-cleanup race entirely. Once
        # the exclusive link is identity-verified, a later directory-fsync
        # failure cannot make the published result untrue.
        with suppress(OSError):
            os.fsync(workspace_fd)
    finally:
        os.close(staging_fd)


def supervise_stage(
    request_path: Path,
    result_path: Path,
    *,
    popen: PopenFactory = _default_popen,
    clock: Clock = time.monotonic,
    sleep: Sleeper = time.sleep,
    status_reader: StatusReader = _read_child_status,
    getrusage: RusageReader = _child_rusage_kib,
) -> StageResult:
    """Consume one private request and exclusively publish one private result."""
    request_path = _absolute_lexical(request_path)
    result_path = _absolute_lexical(result_path)
    if request_path.parent != result_path.parent:
        raise StageContractError("request and result must share the same private workspace")
    workspace = request_path.parent
    request_name = _safe_output_name(request_path.name, field="request")
    result_name = _safe_output_name(result_path.name, field="result")
    workspace_fd = _open_private_workspace(workspace)
    identity = _workspace_identity(workspace_fd)
    try:
        request = _load_request_at(workspace_fd, request_name)
        names = (request_name, result_name, request.stdout, request.stderr)
        if len(set(names)) != len(names):
            raise StageContractError("request, result, stdout, and stderr names must not collide")
        if _name_exists(workspace_fd, result_name):
            raise StageContractError("private result already exists")
        result = _run_stage_at(
            request,
            workspace_fd=workspace_fd,
            popen=popen,
            clock=clock,
            sleep=sleep,
            status_reader=status_reader,
            getrusage=getrusage,
        )
        _require_workspace_identity(workspace, workspace_fd, identity)
        _publish_private_result(workspace_fd, result_name, result)
        return result
    finally:
        os.close(workspace_fd)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the private request/result CLI without mirroring the child exit code."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        return 2
    try:
        supervise_stage(Path(arguments[0]), Path(arguments[1]))
    except StageContractError:
        return 2
    except OSError, StageSupervisorError:
        return 1
    return 0
