"""Private one-child stage supervision for binding NFR-001 RSS measurements."""

import ctypes
import errno
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import IO, cast

import pytest

from docmend.scale_stage import (
    POLL_INTERVAL_SECONDS,
    StageContractError,
    StageRequest,
    StageResult,
    StageSupervisorError,
    load_stage_request,
    main,
    run_stage,
    supervise_stage,
)


def _private_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "private-stage"
    workspace.mkdir(mode=0o700)
    workspace.chmod(0o700)
    return workspace


def _request_document(**updates: object) -> dict[str, object]:
    document: dict[str, object] = {
        "schema": "docmend/scale-stage-request",
        "schema_version": "1.0",
        "stage": "scan",
        "argv": [sys.executable, "-c", "print('synthetic')"],
        "cwd": "/synthetic/stage-cwd",
        "environment": {"SYNTHETIC_STAGE": "1"},
        "stdout": "stage.stdout",
        "stderr": "stage.stderr",
    }
    document.update(updates)
    return document


def _write_request(workspace: Path, document: Mapping[str, object]) -> Path:
    request_path = workspace / "request.json"
    request_path.write_text(json.dumps(document), encoding="utf-8")
    request_path.chmod(0o600)
    return request_path


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)


def _ctypes_int(value: object) -> int:
    return cast("ctypes.c_int", value).value


def _ctypes_bytes(value: object) -> bytes | None:
    return cast("ctypes.c_char_p", value).value


class _FakeProcess:
    def __init__(self, poll_results: Sequence[int | None], *, wait_result: int) -> None:
        self.pid = 4321
        self._poll_results = list(poll_results)
        self._wait_result = wait_result
        self.poll_calls = 0
        self.wait_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        self.poll_calls += 1
        if self._poll_results:
            return self._poll_results.pop(0)
        return self._wait_result

    def wait(self) -> int:
        self.wait_calls += 1
        return self._wait_result

    def kill(self) -> None:
        self.kill_calls += 1

    def __enter__(self) -> _FakeProcess:
        raise AssertionError("Popen must not be used as a context manager")

    def __exit__(self, *_args: object) -> None:
        raise AssertionError("Popen must not be used as a context manager")


class _WaitFailureProcess(_FakeProcess):
    def wait(self) -> int:
        self.wait_calls += 1
        raise OSError("synthetic wait failure")


class _PollFailureProcess(_FakeProcess):
    def poll(self) -> int | None:
        self.poll_calls += 1
        raise RuntimeError("synthetic poll failure")


class TestStageRequestBoundary:
    def test_request__round_trips_the_exact_private_contract(self) -> None:
        request = StageRequest.from_document(_request_document())

        assert request.stage == "scan"
        assert request.argv == (sys.executable, "-c", "print('synthetic')")
        assert request.cwd == Path("/synthetic/stage-cwd")
        assert dict(request.environment) == {"SYNTHETIC_STAGE": "1"}
        assert request.stdout == "stage.stdout"
        assert request.stderr == "stage.stderr"
        assert request.to_document() == _request_document()

    @pytest.mark.parametrize(
        "document",
        [
            {},
            _request_document(extra="forbidden"),
            _request_document(argv=[]),
            _request_document(argv=[sys.executable, 7]),
            _request_document(argv=[""]),
            _request_document(environment=[]),
            _request_document(environment={"": "value"}),
            _request_document(environment={"BAD=KEY": "value"}),
            _request_document(environment={"BAD": "nul\x00value"}),
            _request_document(environment={"PYTHONTRACEMALLOC": "25"}),
            _request_document(environment={"LD_PRELOAD": "/synthetic/inject.so"}),
            _request_document(environment={"LD_DEBUG": "libs"}),
            _request_document(environment={"LD_PROFILE": "libsynthetic.so"}),
            _request_document(environment={"MALLOC_TRACE": "trace.out"}),
            _request_document(environment={"ASAN_OPTIONS": "detect_leaks=1"}),
            _request_document(environment={"LLVM_PROFILE_FILE": "profile.profraw"}),
            _request_document(environment={"COVERAGE_PROCESS_START": "config"}),
            _request_document(environment={"SYNTHETIC_API_TOKEN": "not-a-real-token"}),
            _request_document(cwd="relative"),
            _request_document(cwd="../relative-escape"),
            _request_document(stdout="../escape.stdout"),
            _request_document(stdout="nested/output.stdout"),
            _request_document(stderr="/absolute.stderr"),
            _request_document(stdout="same", stderr="same"),
        ],
    )
    def test_request__rejects_missing_unknown_or_unsafe_fields(
        self, document: dict[str, object]
    ) -> None:
        with pytest.raises(StageContractError):
            StageRequest.from_document(document)

    @pytest.mark.parametrize(
        "argv",
        [
            [sys.executable, "-Xtracemalloc", "-c", "pass"],
            [sys.executable, "-Xtracemalloc=7", "-c", "pass"],
            [sys.executable, "-X", "tracemalloc", "-c", "pass"],
            [sys.executable, "-X", "tracemalloc=7", "-c", "pass"],
            [
                sys.executable,
                "--check-hash-based-pycs",
                "always",
                "-Xtracemalloc=7",
                "-c",
                "pass",
            ],
        ],
    )
    def test_request__rejects_every_python_tracemalloc_option_encoding(
        self, argv: list[str]
    ) -> None:
        with pytest.raises(StageContractError, match="tracemalloc"):
            StageRequest.from_document(_request_document(argv=argv))

    @pytest.mark.parametrize(
        "argv",
        [
            ["/usr/bin/env", sys.executable, "-Xtracemalloc=1", "-c", "pass"],
            ["env", sys.executable, "-X", "tracemalloc", "-c", "pass"],
            [
                "/usr/bin/env",
                "PYTHONTRACEMALLOC=1",
                sys.executable,
                "-c",
                "pass",
            ],
        ],
    )
    def test_request__rejects_environment_launcher_tracing_bypasses(self, argv: list[str]) -> None:
        with pytest.raises(StageContractError, match="environment launcher"):
            StageRequest.from_document(_request_document(argv=argv))

    @pytest.mark.parametrize(
        "document",
        [
            _request_document(argv=[sys.executable, "\ud800"]),
            _request_document(cwd="/synthetic/\ud800"),
            _request_document(environment={"SYNTHETIC": "\ud800"}),
            _request_document(environment={"SYNTHETIC\ud800": "value"}),
            _request_document(stdout="stage\ud800.stdout"),
            _request_document(stderr="stage\ud800.stderr"),
        ],
    )
    def test_request__rejects_non_scalar_unicode_strings(self, document: dict[str, object]) -> None:
        with pytest.raises(StageContractError, match="Unicode"):
            StageRequest.from_document(document)

    @pytest.mark.parametrize(
        "argv",
        [
            [sys.executable, "-X", "dev", "-c", "pass"],
            [sys.executable, "-c", "pass", "-Xtracemalloc"],
            ["synthetic-command", "--label=-Xtracemalloc"],
            ["synthetic-command", "tracemalloc"],
        ],
    )
    def test_request__does_not_over_reject_ordinary_arguments(self, argv: list[str]) -> None:
        request = StageRequest.from_document(_request_document(argv=argv))
        assert request.argv == tuple(argv)

    def test_request_file__rejects_duplicate_keys_and_non_finite_numbers(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        duplicate = workspace / "duplicate.json"
        duplicate.write_text(
            '{"schema":"docmend/scale-stage-request","schema":"docmend/scale-stage-request"}',
            encoding="utf-8",
        )
        duplicate.chmod(0o600)
        with pytest.raises(StageContractError, match="duplicate"):
            load_stage_request(duplicate)

        non_finite = _write_request(workspace, _request_document(environment={"X": float("nan")}))
        with pytest.raises(StageContractError, match="finite"):
            load_stage_request(non_finite)

    def test_request_file__oversized_integer_is_a_contract_error_and_cli_exit_two(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = workspace / "oversized.json"
        request.write_text('{"oversized":' + ("9" * 100_000) + "}", encoding="utf-8")
        request.chmod(0o600)
        result = workspace / "result.json"

        with pytest.raises(StageContractError, match="strict JSON"):
            load_stage_request(request)
        assert main([str(request), str(result)]) == 2
        assert not result.exists()

    def test_request_file__excessive_nesting_is_a_contract_error_and_cli_exit_two(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = workspace / "nested.json"
        request.write_text(("[" * 100_000) + ("]" * 100_000), encoding="utf-8")
        request.chmod(0o600)
        result = workspace / "result.json"

        with pytest.raises(StageContractError, match="strict JSON"):
            load_stage_request(request)
        assert main([str(request), str(result)]) == 2
        assert not result.exists()

    def test_request_file__decoder_value_error_is_a_contract_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(workspace, _request_document())

        def fail_decode(*_args: object, **_kwargs: object) -> object:
            raise ValueError("synthetic decoder limit")

        monkeypatch.setattr(scale_stage.json, "loads", fail_decode)
        with pytest.raises(StageContractError, match="strict JSON"):
            load_stage_request(request)

    @pytest.mark.parametrize("mode", [0o400, 0o640, 0o644])
    def test_request_file__requires_exact_private_mode(self, tmp_path: Path, mode: int) -> None:
        workspace = _private_workspace(tmp_path)
        request_path = _write_request(workspace, _request_document())
        request_path.chmod(mode)
        with pytest.raises(StageContractError, match="0600"):
            load_stage_request(request_path)

    def test_request_file__rejects_symlink_even_to_private_regular_file(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        target = _write_request(workspace, _request_document())
        link = workspace / "request-link.json"
        link.symlink_to(target.name)
        with pytest.raises(StageContractError, match="regular no-follow"):
            load_stage_request(link)


class TestStageResultBoundary:
    def test_result__rejects_booleans_as_integers_and_non_finite_elapsed(self) -> None:
        values: dict[str, object] = {
            "schema": "docmend/scale-stage-result",
            "schema_version": "1.0",
            "stage": "scan",
            "completed": True,
            "exit_code": 0,
            "elapsed_seconds": 1.0,
            "peak_rss_bytes": 1024,
            "vm_swap_peak_bytes": 0,
            "tracing_enabled": False,
            "stdout": "stage.stdout",
            "stderr": "stage.stderr",
            "error_code": None,
        }
        for field, invalid in (
            ("exit_code", True),
            ("peak_rss_bytes", False),
            ("vm_swap_peak_bytes", True),
            ("elapsed_seconds", float("inf")),
        ):
            document = dict(values)
            document[field] = invalid
            with pytest.raises(StageContractError):
                StageResult.from_document(document)

    @pytest.mark.parametrize("error_code", [[], {}])
    def test_result__rejects_unhashable_error_codes_as_contract_errors(
        self, error_code: object
    ) -> None:
        document: dict[str, object] = {
            "schema": "docmend/scale-stage-result",
            "schema_version": "1.0",
            "stage": "scan",
            "completed": False,
            "exit_code": None,
            "elapsed_seconds": 1.0,
            "peak_rss_bytes": None,
            "vm_swap_peak_bytes": None,
            "tracing_enabled": False,
            "stdout": "stage.stdout",
            "stderr": "stage.stderr",
            "error_code": error_code,
        }
        with pytest.raises(StageContractError, match="error_code"):
            StageResult.from_document(document)


class TestRunStage:
    def test_run_stage__launches_one_fixed_child_waits_once_and_converts_linux_rss(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        process = _FakeProcess([None, None, 0], wait_result=7)
        popen_calls: list[tuple[tuple[str, ...], dict[str, object]]] = []
        status_calls: list[int] = []
        sleeps: list[float] = []
        clock_values = iter([10.0, 12.5])
        rusage_calls = 0
        monkeypatch.setenv("SYNTHETIC_PARENT_SECRET", "must-not-be-inherited")
        monkeypatch.setenv("COVERAGE_PROCESS_START", "must-not-be-inherited")

        def popen(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _FakeProcess:
            assert stdout.fileno() >= 0
            assert stderr.fileno() >= 0
            popen_calls.append(
                (
                    tuple(argv),
                    {
                        "shell": shell,
                        "stdin": stdin,
                        "close_fds": close_fds,
                        "cwd": cwd,
                        "env": dict(env),
                    },
                )
            )
            return process

        def read_status(pid: int) -> str:
            status_calls.append(pid)
            return f"Name:\tsynthetic\nVmSwap:\t{len(status_calls) - 1} kB\n"

        def getrusage() -> int:
            nonlocal rusage_calls
            assert process.wait_calls == 1
            rusage_calls += 1
            return 321

        result = run_stage(
            request,
            workspace=workspace,
            popen=popen,
            clock=lambda: next(clock_values),
            sleep=sleeps.append,
            status_reader=read_status,
            getrusage=getrusage,
        )

        assert len(popen_calls) == 1
        argv, options = popen_calls[0]
        assert argv == request.argv
        assert options["shell"] is False
        assert options["stdin"] == subprocess.DEVNULL
        assert options["close_fds"] is True
        assert options["cwd"] == workspace
        environment = cast("dict[str, str]", options["env"])
        assert environment["PYTHONNOUSERSITE"] == "1"
        assert "PYTHONTRACEMALLOC" not in environment
        assert "PYTHONPATH" not in environment
        assert "PYTHONHOME" not in environment
        assert "SYNTHETIC_PARENT_SECRET" not in environment
        assert "COVERAGE_PROCESS_START" not in environment
        assert process.wait_calls == 1
        assert rusage_calls == 1
        assert sleeps == [POLL_INTERVAL_SECONDS, POLL_INTERVAL_SECONDS]
        assert status_calls == [process.pid, process.pid, process.pid]
        assert result.completed is True
        assert result.exit_code == 7
        assert result.elapsed_seconds == 2.5
        assert result.peak_rss_bytes == 321 * 1024
        assert result.vm_swap_peak_bytes == 2 * 1024
        assert result.tracing_enabled is False
        assert result.error_code is None
        assert _mode(workspace / request.stdout) == 0o600
        assert _mode(workspace / request.stderr) == 0o600

    @pytest.mark.parametrize(
        "status_or_error",
        ["Name:\tmissing\n", "VmSwap: malformed kB\n", OSError("synthetic unavailable")],
    )
    def test_run_stage__unavailable_swap_is_none_without_invalidating_completed_rss(
        self, tmp_path: Path, status_or_error: str | OSError
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        process = _FakeProcess([0], wait_result=0)
        clocks = iter([1.0, 1.25])

        def popen(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _FakeProcess:
            _ = (argv, shell, stdin, close_fds, cwd, stdout, stderr, env)
            return process

        def read_status(_pid: int) -> str:
            if isinstance(status_or_error, OSError):
                raise status_or_error
            return status_or_error

        result = run_stage(
            request,
            workspace=workspace,
            popen=popen,
            clock=lambda: next(clocks),
            sleep=lambda _seconds: None,
            status_reader=read_status,
            getrusage=lambda: 1,
        )

        assert result.completed is True
        assert result.exit_code == 0
        assert result.peak_rss_bytes == 1024
        assert result.vm_swap_peak_bytes is None
        assert process.wait_calls == 1

    def test_run_stage__spawn_failure_is_strict_incomplete_without_wait_or_rusage(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        clocks = iter([4.0, 4.5])
        rusage_calls = 0

        def popen(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _FakeProcess:
            _ = (argv, shell, stdin, close_fds, cwd, stdout, stderr, env)
            raise OSError("private executable path")

        def getrusage() -> int:
            nonlocal rusage_calls
            rusage_calls += 1
            return 1

        result = run_stage(
            request,
            workspace=workspace,
            popen=popen,
            clock=lambda: next(clocks),
            sleep=lambda _seconds: None,
            status_reader=lambda _pid: "VmSwap: 0 kB\n",
            getrusage=getrusage,
        )

        assert result.completed is False
        assert result.exit_code is None
        assert result.elapsed_seconds == 0.5
        assert result.peak_rss_bytes is None
        assert result.vm_swap_peak_bytes is None
        assert result.error_code == "spawn-failed"
        assert rusage_calls == 0
        assert "private" not in json.dumps(result.to_document())

    def test_run_stage__closes_stdout_if_stderr_fdopen_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        real_fdopen = cast("Callable[[int, str], IO[bytes]]", scale_stage.os.fdopen)
        opened: list[IO[bytes]] = []

        def fail_second_fdopen(fd: int, mode: str) -> IO[bytes]:
            if opened:
                raise OSError("synthetic stderr fdopen failure")
            stream = real_fdopen(fd, mode)
            opened.append(stream)
            return stream

        monkeypatch.setattr(scale_stage.os, "fdopen", fail_second_fdopen)
        with pytest.raises(OSError, match="stderr fdopen"):
            run_stage(request, workspace=workspace)

        assert len(opened) == 1
        assert opened[0].closed

    def test_run_stage__wait_failure_reaps_once_closes_outputs_and_skips_rusage(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        process = _WaitFailureProcess([0], wait_result=0)
        clocks = iter([2.0, 2.75])
        captured_streams: list[IO[bytes]] = []

        def popen(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _WaitFailureProcess:
            _ = (argv, shell, stdin, close_fds, cwd, env)
            captured_streams.extend((stdout, stderr))
            return process

        def forbidden_rusage() -> int:
            raise AssertionError("rusage must follow a successful wait")

        result = run_stage(
            request,
            workspace=workspace,
            popen=popen,
            clock=lambda: next(clocks),
            sleep=lambda _seconds: None,
            status_reader=lambda _pid: "VmSwap: 0 kB\n",
            getrusage=forbidden_rusage,
        )

        assert process.wait_calls == 1
        assert process.kill_calls == 1
        assert all(stream.closed for stream in captured_streams)
        assert result.completed is False
        assert result.exit_code is None
        assert result.peak_rss_bytes is None
        assert result.vm_swap_peak_bytes is None
        assert result.error_code == "reap-failed"
        assert result.elapsed_seconds == 0.75

    @pytest.mark.parametrize("failing_boundary", ["status", "sleep", "poll"])
    def test_run_stage__telemetry_boundary_failure_still_waits_once(
        self, tmp_path: Path, failing_boundary: str
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        process: _FakeProcess = (
            _PollFailureProcess([], wait_result=0)
            if failing_boundary == "poll"
            else _FakeProcess([None, 0], wait_result=0)
        )
        clocks = iter([3.0, 3.5])

        def popen(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _FakeProcess:
            _ = (argv, shell, stdin, close_fds, cwd, stdout, stderr, env)
            return process

        def read_status(_pid: int) -> str:
            if failing_boundary == "status":
                raise RuntimeError("synthetic status failure")
            return "VmSwap: 0 kB\n"

        def sleep(_seconds: float) -> None:
            if failing_boundary == "sleep":
                raise RuntimeError("synthetic sleep failure")

        result = run_stage(
            request,
            workspace=workspace,
            popen=popen,
            clock=lambda: next(clocks),
            sleep=sleep,
            status_reader=read_status,
            getrusage=lambda: 2,
        )

        assert process.wait_calls == 1
        assert result.completed is True
        assert result.peak_rss_bytes == 2 * 1024
        assert result.vm_swap_peak_bytes is None

    @pytest.mark.parametrize("unsafe_kind", ["regular", "symlink", "fifo"])
    def test_run_stage__refuses_existing_symlink_or_fifo_output_without_launch(
        self, tmp_path: Path, unsafe_kind: str
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        output = workspace / request.stdout
        if unsafe_kind == "regular":
            output.write_text("sentinel", encoding="utf-8")
            output.chmod(0o600)
        elif unsafe_kind == "symlink":
            target = workspace / "symlink-target"
            target.write_text("sentinel", encoding="utf-8")
            target.chmod(0o600)
            output.symlink_to(target.name)
        else:
            os.mkfifo(output, mode=0o600)
        popen_calls = 0

        def popen(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _FakeProcess:
            nonlocal popen_calls
            _ = (argv, shell, stdin, close_fds, cwd, stdout, stderr, env)
            popen_calls += 1
            return _FakeProcess([0], wait_result=0)

        with pytest.raises(StageContractError, match="already exists or collides"):
            run_stage(request, workspace=workspace, popen=popen)
        assert popen_calls == 0
        output_mode = os.lstat(output).st_mode
        assert {
            "regular": stat.S_ISREG,
            "symlink": stat.S_ISLNK,
            "fifo": stat.S_ISFIFO,
        }[unsafe_kind](output_mode)

    def test_run_stage__stderr_collision_preserves_new_private_stdout(self, tmp_path: Path) -> None:
        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        stderr = workspace / request.stderr
        stderr.write_text("sentinel", encoding="utf-8")
        stderr.chmod(0o600)

        with pytest.raises(StageContractError, match="already exists or collides"):
            run_stage(request, workspace=workspace)

        stdout = workspace / request.stdout
        assert stdout.is_file()
        assert _mode(stdout) == 0o600
        assert stdout.read_bytes() == b""
        assert stderr.read_text(encoding="utf-8") == "sentinel"

    def test_run_stage__output_validation_failure_preserves_substituted_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        stdout = workspace / request.stdout

        def substitute_then_fail(_fd: int, _mode: int) -> None:
            stdout.unlink()
            stdout.symlink_to("synthetic-unknown-output")
            raise OSError("synthetic output validation failure")

        monkeypatch.setattr(scale_stage.os, "fchmod", substitute_then_fail)
        with pytest.raises(OSError, match="output validation"):
            run_stage(request, workspace=workspace)

        assert stdout.is_symlink()

    def test_run_stage__stderr_collision_preserves_name_substituted_after_stdout_close(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = StageRequest.from_document(_request_document(cwd=str(workspace)))
        stdout = workspace / request.stdout
        stderr = workspace / request.stderr
        stderr.write_text("sentinel", encoding="utf-8")
        stderr.chmod(0o600)
        real_close = scale_stage.os.close
        substituted = False

        def substitute_after_close(fd: int) -> None:
            nonlocal substituted
            real_close(fd)
            if not substituted and stdout.is_file():
                stdout.unlink()
                stdout.symlink_to("synthetic-unknown-output")
                substituted = True

        monkeypatch.setattr(scale_stage.os, "close", substitute_after_close)
        with pytest.raises(StageContractError, match="already exists or collides"):
            run_stage(request, workspace=workspace)

        assert substituted is True
        assert stdout.is_symlink()
        assert stderr.read_text(encoding="utf-8") == "sentinel"


class TestPrivateWorkspaceAndPublication:
    @pytest.mark.parametrize("mode", [0o755, 0o750, 0o770])
    def test_supervisor__requires_exact_0700_workspace(self, tmp_path: Path, mode: int) -> None:
        workspace = _private_workspace(tmp_path)
        request = _write_request(workspace, _request_document())
        workspace.chmod(mode)
        with pytest.raises(StageContractError, match="0700"):
            supervise_stage(request, workspace / "result.json")

    def test_supervisor__rejects_workspace_symlink(self, tmp_path: Path) -> None:
        target = _private_workspace(tmp_path)
        request = _write_request(target, _request_document())
        link = tmp_path / "workspace-link"
        link.symlink_to(target, target_is_directory=True)
        with pytest.raises(StageContractError, match="symlink"):
            supervise_stage(link / request.name, link / "result.json")

    def test_supervisor__requires_existing_real_non_symlink_cwd(self, tmp_path: Path) -> None:
        workspace = _private_workspace(tmp_path)
        missing_request = _write_request(
            workspace, _request_document(cwd=str(workspace / "missing"))
        )
        with pytest.raises(StageContractError, match="cwd"):
            supervise_stage(missing_request, workspace / "missing-result.json")

        real_cwd = workspace / "real-cwd"
        real_cwd.mkdir()
        cwd_link = workspace / "cwd-link"
        cwd_link.symlink_to(real_cwd.name, target_is_directory=True)
        link_request = _write_request(workspace, _request_document(cwd=str(cwd_link)))
        with pytest.raises(StageContractError, match="cwd"):
            supervise_stage(link_request, workspace / "link-result.json")

    def test_supervisor__rejects_result_escape_and_all_name_collisions(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = _write_request(workspace, _request_document())
        with pytest.raises(StageContractError, match="same private workspace"):
            supervise_stage(request, tmp_path / "escaped-result.json")

        for result_name in (request.name, "stage.stdout", "stage.stderr"):
            with pytest.raises(StageContractError, match="collide"):
                supervise_stage(request, workspace / result_name)

    def test_supervisor__publishes_result_exclusively_without_clobber(self, tmp_path: Path) -> None:
        workspace = _private_workspace(tmp_path)
        request = _write_request(workspace, _request_document())
        result = workspace / "result.json"
        result.write_text("sentinel", encoding="utf-8")
        result.chmod(0o600)

        with pytest.raises(StageContractError, match="exists"):
            supervise_stage(request, result)
        assert result.read_text(encoding="utf-8") == "sentinel"

    def test_supervisor__publishes_anonymous_staging_inode(self, tmp_path: Path) -> None:
        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        parsed = supervise_stage(request, result)

        result_stats = result.stat(follow_symlinks=False)
        assert stat.S_ISREG(result_stats.st_mode)
        assert stat.S_IMODE(result_stats.st_mode) == 0o600
        assert StageResult.from_document(json.loads(result.read_text(encoding="utf-8"))) == parsed
        assert list(workspace.glob(".result.json.*.tmp")) == []

    def test_supervisor__anonymous_link_uses_direct_fd_and_destination_dirfd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        real_linkat = scale_stage._LINKAT  # pyright: ignore[reportPrivateUsage]
        assert real_linkat is not None
        calls: list[tuple[object, ...]] = []

        def linkat(*arguments: object) -> int:
            calls.append(arguments)
            return real_linkat(*arguments)

        monkeypatch.setattr(scale_stage, "_LINKAT", linkat)
        parsed = supervise_stage(request, result)

        assert parsed.completed is True
        assert len(calls) == 1
        source_fd, source, destination_fd, destination, flags = calls[0]
        assert _ctypes_int(source_fd) >= 0
        assert _ctypes_bytes(source) == b""
        assert _ctypes_int(destination_fd) >= 0
        assert _ctypes_bytes(destination) == b"result.json"
        assert _ctypes_int(flags) == 0x1000

    def test_supervisor__direct_capability_failure_uses_safe_proc_fd_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        real_linkat = scale_stage._LINKAT  # pyright: ignore[reportPrivateUsage]
        assert real_linkat is not None
        calls: list[tuple[object, ...]] = []

        def linkat(*arguments: object) -> int:
            calls.append(arguments)
            if len(calls) == 1:
                ctypes.set_errno(errno.ENOENT)
                return -1
            return real_linkat(*arguments)

        monkeypatch.setattr(scale_stage, "_LINKAT", linkat)
        parsed = supervise_stage(request, result)

        assert parsed.completed is True
        assert len(calls) == 2
        direct_fd = _ctypes_int(calls[0][0])
        assert direct_fd >= 0
        assert _ctypes_bytes(calls[0][1]) == b""
        assert _ctypes_int(calls[0][2]) == _ctypes_int(calls[1][2])
        assert _ctypes_bytes(calls[0][3]) == _ctypes_bytes(calls[1][3]) == b"result.json"
        assert _ctypes_int(calls[0][4]) == 0x1000
        assert _ctypes_int(calls[1][0]) == -100
        assert _ctypes_bytes(calls[1][1]) == f"/proc/self/fd/{direct_fd}".encode("ascii")
        assert _ctypes_int(calls[1][4]) == 0x400

    def test_supervisor__fallback_collision_preserves_existing_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        real_linkat = scale_stage._LINKAT  # pyright: ignore[reportPrivateUsage]
        assert real_linkat is not None
        calls = 0

        def linkat(*arguments: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                ctypes.set_errno(errno.ENOENT)
                return -1
            result.write_text("sentinel", encoding="utf-8")
            result.chmod(0o600)
            return real_linkat(*arguments)

        monkeypatch.setattr(scale_stage, "_LINKAT", linkat)
        with pytest.raises(StageSupervisorError, match="collision"):
            supervise_stage(request, result)

        assert calls == 2
        assert result.read_text(encoding="utf-8") == "sentinel"

    def test_supervisor__unavailable_proc_fallback_fails_without_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        calls = 0

        def unavailable_linkat(*_arguments: object) -> int:
            nonlocal calls
            calls += 1
            ctypes.set_errno(errno.ENOENT)
            return -1

        monkeypatch.setattr(scale_stage, "_LINKAT", unavailable_linkat)
        with pytest.raises(StageSupervisorError, match="publication"):
            supervise_stage(request, result)

        assert calls == 2
        assert not result.exists()

    def test_supervisor__malformed_proc_fallback_target_fails_identity_reconciliation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        calls = 0

        def malformed_linkat(*arguments: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                ctypes.set_errno(errno.ENOENT)
                return -1
            destination_fd = _ctypes_int(arguments[2])
            destination = _ctypes_bytes(arguments[3])
            assert destination is not None
            wrong_fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o600,
                dir_fd=destination_fd,
            )
            try:
                os.write(wrong_fd, b"synthetic-wrong-proc-target")
            finally:
                os.close(wrong_fd)
            return 0

        monkeypatch.setattr(scale_stage, "_LINKAT", malformed_linkat)
        with pytest.raises(StageSupervisorError, match="identity"):
            supervise_stage(request, result)

        assert calls == 2
        assert result.read_bytes() == b"synthetic-wrong-proc-target"

    def test_supervisor__has_no_staging_name_for_stat_to_unlink_substitution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        real_stat = scale_stage.os.stat
        substituted_name: str | None = None

        def substitute_after_stat(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes] | int,
            *,
            dir_fd: int | None = None,
            follow_symlinks: bool = True,
        ) -> os.stat_result:
            nonlocal substituted_name
            details = real_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
            if (
                substituted_name is None
                and isinstance(path, str)
                and path.startswith(".result.json.")
                and path.endswith(".tmp")
                and dir_fd is not None
            ):
                os.unlink(path, dir_fd=dir_fd)
                os.symlink("synthetic-unknown-name", path, dir_fd=dir_fd)
                substituted_name = path
            return details

        monkeypatch.setattr(scale_stage.os, "stat", substitute_after_stat)
        parsed = supervise_stage(request, result)

        assert parsed.completed is True
        assert substituted_name is None
        assert list(workspace.glob(".result.json.*.tmp")) == []

    def test_supervisor__opens_and_holds_one_workspace_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        open_calls = 0
        real_open = cast(
            "Callable[[Path], int]",
            scale_stage._open_private_workspace,  # pyright: ignore[reportPrivateUsage]
        )

        def count_open(path: Path) -> int:
            nonlocal open_calls
            open_calls += 1
            return real_open(path)

        monkeypatch.setattr(scale_stage, "_open_private_workspace", count_open)
        supervise_stage(request, result)
        assert open_calls == 1

    def test_supervisor__rejects_workspace_replacement_during_initial_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(tmp_path)),
        )
        result = workspace / "result.json"
        moved = tmp_path / "original-private-stage"
        real_open = scale_stage.os.open
        replaced = False

        def replace_before_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal replaced
            if not replaced and dir_fd is None and path == workspace and flags & os.O_DIRECTORY:
                replaced = True
                workspace.rename(moved)
                workspace.mkdir(mode=0o700)
                workspace.chmod(0o700)
                _write_request(
                    workspace,
                    _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(tmp_path)),
                )
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(scale_stage.os, "open", replace_before_open)
        with pytest.raises(StageContractError, match=r"workspace.*changed"):
            supervise_stage(request, result)

        assert replaced is True
        assert not result.exists()
        assert not (moved / result.name).exists()

    def test_supervisor__refuses_workspace_replacement_before_publication(
        self, tmp_path: Path
    ) -> None:
        workspace = _private_workspace(tmp_path)
        request = _write_request(workspace, _request_document(cwd=str(workspace)))
        result = workspace / "result.json"
        moved = tmp_path / "moved-private-stage"
        process = _FakeProcess([0], wait_result=0)
        clocks = iter([1.0, 2.0])

        def replace_workspace(
            argv: Sequence[str],
            *,
            shell: bool,
            stdin: int,
            close_fds: bool,
            cwd: Path,
            stdout: IO[bytes],
            stderr: IO[bytes],
            env: Mapping[str, str],
        ) -> _FakeProcess:
            _ = (argv, shell, stdin, close_fds, cwd, stdout, stderr, env)
            workspace.rename(moved)
            workspace.mkdir(mode=0o700)
            workspace.chmod(0o700)
            return process

        with pytest.raises(StageSupervisorError, match=r"workspace.*changed"):
            supervise_stage(
                request,
                result,
                popen=replace_workspace,
                clock=lambda: next(clocks),
                sleep=lambda _seconds: None,
                status_reader=lambda _pid: "VmSwap: 0 kB\n",
                getrusage=lambda: 1,
            )

        assert not result.exists()
        assert not (moved / result.name).exists()

    def test_supervisor__anonymous_publication_never_unlinks_a_staging_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        real_unlink = scale_stage.os.unlink
        staging_unlinks = 0

        def unlink(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            *,
            dir_fd: int | None = None,
        ) -> None:
            nonlocal staging_unlinks
            if isinstance(path, str) and path.startswith(".result.json."):
                staging_unlinks += 1
                raise AssertionError("anonymous publication must not unlink a staging path")
            real_unlink(path, dir_fd=dir_fd)

        monkeypatch.setattr(scale_stage.os, "unlink", unlink)
        parsed = supervise_stage(request, result)
        assert staging_unlinks == 0
        assert parsed.completed is True
        assert StageResult.from_document(json.loads(result.read_text(encoding="utf-8"))) == parsed

    def test_supervisor__post_link_directory_fsync_failure_keeps_successful_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from docmend import scale_stage

        workspace = _private_workspace(tmp_path)
        request = _write_request(
            workspace,
            _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
        )
        result = workspace / "result.json"
        real_fsync = scale_stage.os.fsync
        fsync_calls = 0

        def fsync(fd: int) -> None:
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 2:
                raise OSError("synthetic directory fsync failure")
            real_fsync(fd)

        monkeypatch.setattr(scale_stage.os, "fsync", fsync)
        parsed = supervise_stage(request, result)
        assert parsed.completed is True
        assert StageResult.from_document(json.loads(result.read_text(encoding="utf-8"))) == parsed


def test_real_wrapper__captures_private_outputs_and_strips_python_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _private_workspace(tmp_path)
    child = (
        "import json, os, sys; "
        "print(json.dumps({k: os.environ.get(k) for k in "
        "['PYTHONTRACEMALLOC','PYTHONPATH','PYTHONHOME','PYTHONNOUSERSITE','SYNTHETIC']})); "
        "print('synthetic stderr', file=sys.stderr)"
    )
    request = _write_request(
        workspace,
        _request_document(
            argv=[sys.executable, "-c", child],
            cwd=str(workspace),
            environment={
                "PYTHONPATH": "/private/python/path",
                "PYTHONHOME": "/private/python/home",
                "PYTHONNOUSERSITE": "0",
                "SYNTHETIC": "kept",
            },
        ),
    )
    result = workspace / "result.json"
    monkeypatch.setenv("PYTHONTRACEMALLOC", "99")
    monkeypatch.setenv("PYTHONPATH", "/private/parent/path")

    completed = subprocess.run(
        [
            sys.executable,
            str(Path("scripts/measure_scale_stage.py").resolve()),
            str(request),
            str(result),
        ],
        check=False,
        cwd=Path(__file__).parents[1],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    result_document: dict[str, object] = json.loads(result.read_text(encoding="utf-8"))
    parsed = StageResult.from_document(result_document)
    assert parsed.completed is True
    assert parsed.exit_code == 0
    assert parsed.peak_rss_bytes is not None
    assert parsed.tracing_enabled is False
    assert _mode(request) == 0o600
    assert _mode(result) == 0o600
    assert _mode(workspace / parsed.stdout) == 0o600
    assert _mode(workspace / parsed.stderr) == 0o600
    child_environment: dict[str, str | None] = json.loads(
        (workspace / parsed.stdout).read_text(encoding="utf-8")
    )
    assert child_environment == {
        "PYTHONTRACEMALLOC": None,
        "PYTHONPATH": None,
        "PYTHONHOME": None,
        "PYTHONNOUSERSITE": "1",
        "SYNTHETIC": "kept",
    }
    assert (workspace / parsed.stderr).read_text(encoding="utf-8") == "synthetic stderr\n"


def test_main__requires_exact_request_and_result_arguments() -> None:
    assert main([]) == 2
    assert main(["only-request.json"]) == 2
    assert main(["request.json", "result.json", "extra"]) == 2


def test_main__rejects_escaped_lone_surrogate_as_contract_status(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    request = _write_request(
        workspace,
        _request_document(cwd=str(workspace), environment={"SYNTHETIC": "\ud800"}),
    )
    result = workspace / "result.json"

    assert main([str(request), str(result)]) == 2
    assert not result.exists()


def test_main__publishes_spawn_failure_as_trustworthy_result(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    request = _write_request(
        workspace,
        _request_document(
            argv=["/synthetic/missing-stage-executable"],
            cwd=str(workspace),
        ),
    )
    result = workspace / "result.json"

    assert main([str(request), str(result)]) == 0
    result_document: dict[str, object] = json.loads(result.read_text(encoding="utf-8"))
    parsed = StageResult.from_document(result_document)
    assert parsed.completed is False
    assert parsed.error_code == "spawn-failed"


def test_main__publication_failure_is_supervisor_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docmend import scale_stage

    workspace = _private_workspace(tmp_path)
    request = _write_request(
        workspace,
        _request_document(argv=[sys.executable, "-c", "pass"], cwd=str(workspace)),
    )
    result = workspace / "result.json"

    def fail_publish(_workspace: Path, _name: str, _result: StageResult) -> None:
        raise StageSupervisorError("synthetic publication failure")

    monkeypatch.setattr(scale_stage, "_publish_private_result", fail_publish)
    assert main([str(request), str(result)]) == 1
    assert not result.exists()


def test_real_wrapper__does_not_mirror_nonzero_child_exit(tmp_path: Path) -> None:
    workspace = _private_workspace(tmp_path)
    request = _write_request(
        workspace,
        _request_document(
            argv=[sys.executable, "-c", "raise SystemExit(7)"],
            cwd=str(workspace),
        ),
    )
    result = workspace / "result.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(Path("scripts/measure_scale_stage.py").resolve()),
            str(request),
            str(result),
        ],
        check=False,
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    result_document: dict[str, object] = json.loads(result.read_text(encoding="utf-8"))
    parsed = StageResult.from_document(result_document)
    assert parsed.completed is True
    assert parsed.exit_code == 7
    assert parsed.peak_rss_bytes is not None
