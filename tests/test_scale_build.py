"""Exact-HEAD installed-wheel candidate build contracts for NFR-001."""

import hashlib
import json
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import FrozenInstanceError, is_dataclass
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from docmend.scale_build import (
    BuildContractError,
    BuildRequest,
    CommandResult,
    inspect_candidate_source,
    prepare_candidate,
    recheck_candidate_source,
)


def _git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def candidate_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "candidate"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "Synthetic Builder")
    _git(repository, "config", "user.email", "synthetic@example.invalid")
    _git(repository, "config", "commit.gpgsign", "false")
    _git(repository, "config", "core.hooksPath", "/dev/null")
    (repository / "pyproject.toml").write_text(
        """[project]
name = "docmend"
version = "1.0.2"
requires-python = ">=3.14"

[build-system]
requires = ["uv_build==0.11.6"]
build-backend = "uv_build"
""",
        encoding="utf-8",
    )
    (repository / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = ">=3.14"\n',
        encoding="utf-8",
    )
    package = repository / "src/docmend"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "1.0.2"\n', encoding="utf-8")
    (package / "scale_probe.py").write_text("VALUE = 1\n", encoding="utf-8")
    scripts = repository / "scripts"
    scripts.mkdir()
    (scripts / "measure_scale_stage.py").write_text(
        "from docmend.scale_probe import VALUE\n",
        encoding="utf-8",
    )
    _git(repository, "add", "pyproject.toml", "uv.lock", "src", "scripts")
    _git(repository, "commit", "-qm", "synthetic candidate")
    return repository


def test_scale_build_module__is_available_for_qualification() -> None:
    assert find_spec("docmend.scale_build") is not None


def test_scale_build_module__exports_frozen_contract_surface() -> None:
    module = import_module("docmend.scale_build")

    assert module.QUALIFICATION_UV_VERSION == "0.11.6"
    for name in ("SourceProvenance", "BuildRequest", "CandidateBuild"):
        contract = getattr(module, name, None)
        assert contract is not None
        assert is_dataclass(contract)
    assert getattr(module, "inspect_candidate_source", None) is not None
    assert getattr(module, "recheck_candidate_source", None) is not None
    assert getattr(module, "prepare_candidate", None) is not None


def test_inspect_candidate_source__binds_clean_committed_bytes(
    candidate_repository: Path,
) -> None:
    pyproject = _git(candidate_repository, "show", "HEAD:pyproject.toml").stdout
    lock = _git(candidate_repository, "show", "HEAD:uv.lock").stdout

    source = inspect_candidate_source(candidate_repository)

    assert source.repository == candidate_repository.resolve()
    assert source.commit == _git(candidate_repository, "rev-parse", "HEAD").stdout.decode().strip()
    assert source.package_name == "docmend"
    assert source.package_version == "1.0.2"
    assert source.build_backend == "uv_build"
    assert source.build_backend_version == "0.11.6"
    assert source.build_frontend_version == "0.11.6"
    assert source.pyproject_sha256 == f"sha256:{hashlib.sha256(pyproject).hexdigest()}"
    assert source.lock_sha256 == f"sha256:{hashlib.sha256(lock).hexdigest()}"
    assert source.pyproject_bytes == pyproject
    assert source.lock_bytes == lock
    with pytest.raises(FrozenInstanceError):
        source.commit = "b" * 40  # type: ignore[misc]


@pytest.mark.parametrize("dirty_name", ["pyproject.toml", "untracked.txt"])
def test_inspect_candidate_source__rejects_dirty_or_untracked_tree(
    candidate_repository: Path, dirty_name: str
) -> None:
    path = candidate_repository / dirty_name
    path.write_text("changed\n", encoding="utf-8")

    with pytest.raises(BuildContractError, match="clean"):
        inspect_candidate_source(candidate_repository)


def test_inspect_candidate_source__rejects_unborn_repository(tmp_path: Path) -> None:
    repository = tmp_path / "unborn"
    repository.mkdir()
    _git(repository, "init", "-q")

    with pytest.raises(BuildContractError, match=r"HEAD|unborn"):
        inspect_candidate_source(repository)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('name = "docmend"', 'name = "other"', "package"),
        ('requires = ["uv_build==0.11.6"]', 'requires = ["uv_build>=0.11"]', "exact"),
        ('build-backend = "uv_build"', 'build-backend = "setuptools.build_meta"', "backend"),
    ],
)
def test_inspect_candidate_source__rejects_wrong_package_or_backend_contract(
    candidate_repository: Path, old: str, new: str, message: str
) -> None:
    path = candidate_repository / "pyproject.toml"
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    _git(candidate_repository, "add", "pyproject.toml")
    _git(candidate_repository, "commit", "-qm", "change contract")

    with pytest.raises(BuildContractError, match=message):
        inspect_candidate_source(candidate_repository)


def test_recheck_candidate_source__rejects_changed_head(
    candidate_repository: Path,
) -> None:
    source = inspect_candidate_source(candidate_repository)
    (candidate_repository / "new.txt").write_text("new commit\n", encoding="utf-8")
    _git(candidate_repository, "add", "new.txt")
    _git(candidate_repository, "commit", "-qm", "move head")

    with pytest.raises(BuildContractError, match="changed"):
        recheck_candidate_source(source)


class FakeBuildCommands:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []
        self.uv_version = "0.11.6"
        self.wheel_count = 1
        self.symlink_wheel = False
        self.metadata_name = "docmend"
        self.metadata_version = "1.0.2"
        self.pip_check_exit = 0
        self.venv_exit = 0
        self.export_exit = 0
        self.import_origin_escape = False
        self.dirty_after_build: Path | None = None
        self.build_source: Path | None = None
        self.symlink_python = False
        self.uv_wheel_gitignore = True
        self.replace_runtime_during_install = False
        self.replace_wheel_during_install = False
        self.replace_python_during_import_proof = False
        self.aba_runtime_during_install = False
        self.aba_wheel_during_install = False
        self.executable_mode = 0o700
        self.venv_spawn_error = False
        self.installer_inputs: list[bytes] = []
        self.passed_fds: list[tuple[int, ...]] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        environment: Mapping[str, str],
        pass_fds: Sequence[int] = (),
    ) -> CommandResult:
        command = tuple(argv)
        self.calls.append((command, cwd, dict(environment)))
        self.passed_fds.append(tuple(pass_fds))
        if command[:2] == ("uv", "--version"):
            return CommandResult(0, f"uv {self.uv_version}\n".encode(), b"")
        if command[0] == "git":
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                check=False,
                capture_output=True,
            )
            return CommandResult(completed.returncode, completed.stdout, completed.stderr)
        if command[:3] == ("uv", "--no-config", "build"):
            wheel_dir = Path(command[command.index("--out-dir") + 1])
            self.build_source = Path(command[-1])
            if self.uv_wheel_gitignore:
                (wheel_dir / ".gitignore").write_text("*\n", encoding="utf-8")
            for index in range(self.wheel_count):
                wheel = wheel_dir / f"docmend-1.0.2-py3-none-any{index or ''}.whl"
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr(
                        "docmend-1.0.2.dist-info/METADATA",
                        "Metadata-Version: 2.4\n"
                        f"Name: {self.metadata_name}\n"
                        f"Version: {self.metadata_version}\n",
                    )
            if self.symlink_wheel:
                wheel = next(wheel_dir.glob("*.whl"))
                wheel.unlink()
                target = wheel_dir.parent / "outside.whl"
                target.write_bytes(b"wheel")
                wheel.symlink_to(target)
            if self.dirty_after_build is not None:
                self.dirty_after_build.write_text("dirty\n", encoding="utf-8")
            return CommandResult(0, b"", b"")
        if command[:3] == ("uv", "--no-config", "venv"):
            if self.venv_spawn_error:
                raise OSError("synthetic venv spawn failure")
            if self.venv_exit:
                return CommandResult(self.venv_exit, b"", b"venv failure")
            venv = Path(command[-1])
            binary = venv / "bin"
            binary.mkdir(parents=True)
            python = binary / "python"
            if self.symlink_python:
                python.symlink_to(Path(sys.executable).resolve())
            else:
                python.write_text("#!/bin/sh\n", encoding="utf-8")
                python.chmod(0o700)
            executable = binary / "docmend"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(self.executable_mode)
            return CommandResult(0, b"", b"")
        if command[:3] == ("uv", "--no-config", "export"):
            if self.export_exit:
                return CommandResult(self.export_exit, b"", b"export failure")
            output = Path(command[command.index("--output-file") + 1])
            output.write_text(
                "dependency==1.0 --hash=sha256:" + "a" * 64 + "\n",
                encoding="utf-8",
            )
            return CommandResult(0, b"", b"")
        if command[:4] == ("uv", "--no-config", "pip", "check"):
            return CommandResult(self.pip_check_exit, b"", b"broken")
        if command[:3] == ("uv", "--no-config", "pip"):
            requirement = Path(command[command.index("-r") + 1]).read_bytes()
            self.installer_inputs.append(requirement)
            if requirement.startswith(b"dependency=="):
                runtime = cwd / "runtime-requirements.txt"
                held = runtime.with_name("held-requirements.txt")
                replacement = runtime.with_name("replacement-requirements.txt")
                replacement.write_text("replacement==1.0\n", encoding="utf-8")
                if self.replace_runtime_during_install:
                    replacement.replace(runtime)
                elif self.aba_runtime_during_install:
                    runtime.replace(held)
                    replacement.replace(runtime)
                    runtime.unlink()
                    held.replace(runtime)
                return CommandResult(0, b"", b"")
            text = requirement.decode("ascii").strip()
            location, expected_hash = text.split(" --hash=", maxsplit=1)
            wheel = Path(unquote(urlsplit(location.split(" @ ", maxsplit=1)[1]).path))
            held = wheel.with_name("held-wheel.whl")
            replacement = wheel.with_name("replacement.whl")
            replacement.write_bytes(b"replacement wheel bytes")
            if self.replace_wheel_during_install:
                replacement.replace(wheel)
            elif self.aba_wheel_during_install:
                wheel.replace(held)
                replacement.replace(wheel)
            actual_hash = "sha256:" + hashlib.sha256(wheel.read_bytes()).hexdigest()
            if self.aba_wheel_during_install:
                wheel.unlink()
                held.replace(wheel)
            if actual_hash != expected_hash:
                return CommandResult(1, b"", b"wheel hash mismatch")
            if replacement.exists():
                replacement.unlink()
            return CommandResult(0, b"", b"")
        if len(command) >= 3 and command[1:3] == ("-I", "-c"):
            if self.replace_python_during_import_proof:
                python = Path(command[0])
                python.write_text("#!/bin/sh\n# permanent replacement\n", encoding="utf-8")
                python.chmod(0o700)
            venv = Path(command[0]).parent.parent
            base = (
                Path("/outside") if self.import_origin_escape else venv / "lib/python/site-packages"
            )
            payload = {
                "docmend": str(base / "docmend/__init__.py"),
                "docmend.scale_build": str(base / "docmend/scale_build.py"),
                "docmend.scale_probe": str(base / "docmend/scale_probe.py"),
            }
            return CommandResult(0, json.dumps(payload).encode(), b"")
        return CommandResult(99, b"", b"unexpected command")


@pytest.fixture
def fake_commands() -> FakeBuildCommands:
    return FakeBuildCommands()


def _build_request(repository: Path, workspace: Path) -> BuildRequest:
    return BuildRequest(
        repository=repository.resolve(),
        workspace=workspace.resolve(strict=False),
        python_executable=Path(sys.executable).resolve(),
    )


def test_inspect_candidate_source__requires_exact_uv_version(
    candidate_repository: Path, fake_commands: FakeBuildCommands
) -> None:
    fake_commands.uv_version = "0.11.5"

    with pytest.raises(BuildContractError, match=r"exact uv 0\.11\.6"):
        inspect_candidate_source(candidate_repository, commands=fake_commands)


@pytest.mark.parametrize("workspace_kind", ["preexisting", "inside-repository"])
def test_prepare_candidate__requires_absent_external_workspace(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    workspace_kind: str,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    if workspace_kind == "preexisting":
        workspace = tmp_path / "existing"
        workspace.mkdir()
    else:
        workspace = candidate_repository / "qualification-workspace"

    with pytest.raises(BuildContractError, match=r"absent|outside"):
        prepare_candidate(
            _build_request(candidate_repository, workspace),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__builds_archived_head_and_runs_exact_install_contract(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    workspace = tmp_path / "qualification"
    request = _build_request(candidate_repository, workspace)

    candidate = prepare_candidate(request, source=source, commands=fake_commands)

    assert candidate.commit == source.commit
    assert candidate.source_snapshot != request.repository
    assert candidate.source_snapshot.is_relative_to(workspace)
    assert fake_commands.build_source == candidate.source_snapshot
    assert (candidate.source_snapshot / "pyproject.toml").read_bytes() == source.pyproject_bytes
    assert (candidate.source_snapshot / "uv.lock").read_bytes() == source.lock_bytes
    assert candidate.wheel_sha256 == (
        "sha256:" + hashlib.sha256(candidate.wheel.read_bytes()).hexdigest()
    )
    assert candidate.package_name == "docmend"
    assert candidate.package_version == "1.0.2"
    assert candidate.build_backend_version == "0.11.6"
    assert candidate.build_frontend_version == "0.11.6"
    assert candidate.venv_python == workspace / "venv/bin/python"
    assert candidate.executable == workspace / "venv/bin/docmend"
    assert workspace.stat().st_mode & 0o777 == 0o700

    commands = [call for call, _cwd, _environment in fake_commands.calls]
    assert (
        "uv",
        "--no-config",
        "build",
        "--wheel",
        "--no-sources",
        "--force-pep517",
        "--out-dir",
        str(workspace / "wheel"),
        str(candidate.source_snapshot),
    ) in commands
    assert (
        "uv",
        "--no-config",
        "venv",
        "--no-project",
        "--python",
        str(Path(sys.executable).resolve()),
        "--no-python-downloads",
        str(workspace / "venv"),
    ) in commands
    assert (
        "uv",
        "--no-config",
        "export",
        "--project",
        str(candidate.source_snapshot),
        "--locked",
        "--no-dev",
        "--no-emit-project",
        "--no-sources",
        "--format",
        "requirements.txt",
        "--output-file",
        str(workspace / "runtime-requirements.txt"),
    ) in commands
    runtime_install = next(command for command in commands if "--only-binary" in command)
    assert runtime_install[:-1] == (
        "uv",
        "--no-config",
        "pip",
        "install",
        "--python",
        str(candidate.venv_python),
        "--require-hashes",
        "--no-deps",
        "--only-binary",
        ":all:",
        "-r",
    )
    assert runtime_install[-1].startswith("/proc/self/fd/")
    wheel_install = next(command for command in commands if "--no-index" in command)
    assert wheel_install[:-1] == (
        "uv",
        "--no-config",
        "pip",
        "install",
        "--python",
        str(candidate.venv_python),
        "--require-hashes",
        "--no-index",
        "--no-deps",
        "-r",
    )
    assert wheel_install[-1].startswith("/proc/self/fd/")
    assert fake_commands.installer_inputs == [
        (workspace / "runtime-requirements.txt").read_bytes(),
        (f"docmend @ {candidate.wheel.as_uri()} --hash={candidate.wheel_sha256}\n").encode("ascii"),
    ]
    assert sum(bool(descriptors) for descriptors in fake_commands.passed_fds) == 2
    assert (
        "uv",
        "--no-config",
        "pip",
        "check",
        "--python",
        str(candidate.venv_python),
    ) in commands
    for _command, _cwd, environment in fake_commands.calls:
        assert "UV_CONFIG_FILE" not in environment


@pytest.mark.parametrize(
    ("wheel_count", "symlink", "message"),
    [(2, False, "one regular"), (1, True, "regular non-symlink")],
)
def test_prepare_candidate__rejects_ambiguous_or_symlink_wheel(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    wheel_count: int,
    symlink: bool,
    message: str,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.wheel_count = wheel_count
    fake_commands.symlink_wheel = symlink

    with pytest.raises(BuildContractError, match=message):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


@pytest.mark.parametrize(
    ("field", "value"), [("metadata_name", "other"), ("metadata_version", "9.9.9")]
)
def test_prepare_candidate__rejects_wheel_metadata_mismatch(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    field: str,
    value: str,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    setattr(fake_commands, field, value)

    with pytest.raises(BuildContractError, match="wheel metadata"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__rejects_pip_check_failure(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.pip_check_exit = 1

    with pytest.raises(BuildContractError, match="pip check"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


@pytest.mark.parametrize("phase", ["venv", "export"])
def test_prepare_candidate__retains_post_wheel_install_failure_checkpoint(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    phase: str,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    setattr(fake_commands, f"{phase}_exit", 1)

    with pytest.raises(BuildContractError) as caught:
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )

    assert caught.value.failure_kind == "install"
    assert caught.value.wheel_sha256 is not None
    assert caught.value.workspace_lease is not None
    caught.value.workspace_lease.close()


def test_prepare_candidate__normalizes_post_wheel_spawn_failure_checkpoint(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.venv_spawn_error = True

    with pytest.raises(BuildContractError) as caught:
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )

    assert caught.value.failure_kind == "install"
    assert caught.value.wheel_sha256 is not None
    assert caught.value.workspace_lease is not None
    caught.value.workspace_lease.close()


@pytest.mark.parametrize(
    "replacement",
    ["runtime", "wheel"],
)
def test_prepare_candidate__rejects_replaced_install_input(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    replacement: str,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    setattr(fake_commands, f"replace_{replacement}_during_install", True)

    with pytest.raises(BuildContractError, match=f"{replacement}.*(?:changed|install)"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__binds_installers_across_path_aba_substitution(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.aba_runtime_during_install = True

    candidate = prepare_candidate(
        _build_request(candidate_repository, tmp_path / "qualification"),
        source=source,
        commands=fake_commands,
    )

    assert (
        fake_commands.installer_inputs[0]
        == (candidate.venv.parent / "runtime-requirements.txt").read_bytes()
    )


def test_prepare_candidate__rejects_wheel_aba_with_hash_bound_install(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.aba_wheel_during_install = True

    with pytest.raises(BuildContractError, match="wheel install failed"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__rejects_non_executable_console_script(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.executable_mode = 0o600

    with pytest.raises(BuildContractError, match=r"candidate executable.*executable"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__rejects_import_origin_escape(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.import_origin_escape = True

    with pytest.raises(BuildContractError, match="import origin"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__rechecks_source_after_build(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.dirty_after_build = candidate_repository / "late-untracked.txt"

    with pytest.raises(BuildContractError, match="clean"):
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )


def test_prepare_candidate__accepts_uv_style_bound_python_symlink(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.symlink_python = True

    candidate = prepare_candidate(
        _build_request(candidate_repository, tmp_path / "qualification"),
        source=source,
        commands=fake_commands,
    )

    assert candidate.venv_python.is_symlink()
    assert candidate.venv_python.resolve() == Path(sys.executable).resolve()
    candidate.require_current_identity()
    candidate.workspace_lease.close()


def test_prepare_candidate__rejects_python_substitution_during_import_proof(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.replace_python_during_import_proof = True

    with pytest.raises(BuildContractError, match=r"candidate Python identity changed") as caught:
        prepare_candidate(
            _build_request(candidate_repository, tmp_path / "qualification"),
            source=source,
            commands=fake_commands,
        )

    assert caught.value.failure_kind == "install"
    assert caught.value.wheel_sha256 is not None
    assert caught.value.workspace_lease is not None
    caught.value.workspace_lease.close()


@pytest.mark.parametrize("artifact", ["executable", "venv-python", "wrapper"])
def test_candidate_build__rejects_permanent_consumer_artifact_substitution(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    artifact: str,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    candidate = prepare_candidate(
        _build_request(candidate_repository, tmp_path / "qualification"),
        source=source,
        commands=fake_commands,
    )
    path = {
        "executable": candidate.executable,
        "venv-python": candidate.venv_python,
        "wrapper": candidate.source_snapshot / "scripts/measure_scale_stage.py",
    }[artifact]
    path.write_bytes(b"permanent replacement\n")
    if artifact != "wrapper":
        path.chmod(0o700)

    try:
        with pytest.raises(BuildContractError, match=r"candidate.*(?:identity|changed)"):
            candidate.require_current_identity()
    finally:
        candidate.workspace_lease.close()


def test_candidate_build__rejects_venv_python_symlink_rebinding(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    fake_commands.symlink_python = True
    candidate = prepare_candidate(
        _build_request(candidate_repository, tmp_path / "qualification"),
        source=source,
        commands=fake_commands,
    )
    replacement = tmp_path / "replacement-python"
    replacement.write_text("#!/bin/sh\n", encoding="utf-8")
    replacement.chmod(0o700)
    candidate.venv_python.unlink()
    candidate.venv_python.symlink_to(replacement)

    try:
        with pytest.raises(BuildContractError, match=r"candidate.*(?:identity|changed)"):
            candidate.require_current_identity()
    finally:
        candidate.workspace_lease.close()


def test_prepare_candidate__rejects_workspace_replaced_between_creation_and_open(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)
    workspace = tmp_path / "qualification"
    held = tmp_path / "held-created-workspace"
    original_chmod = Path.chmod
    replaced = False

    def replace_before_chmod(
        path: Path,
        mode: int,
        *,
        follow_symlinks: bool = True,
    ) -> None:
        nonlocal replaced
        if path == workspace and not replaced:
            replaced = True
            path.replace(held)
            path.mkdir(mode=0o700)
        original_chmod(path, mode, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "chmod", replace_before_chmod)

    with pytest.raises(BuildContractError, match=r"workspace.*(?:identity|safely)"):
        prepare_candidate(
            _build_request(candidate_repository, workspace),
            source=source,
            commands=fake_commands,
        )

    assert replaced


def test_prepare_candidate__accepts_pinned_uv_wheel_directory_marker(
    candidate_repository: Path,
    tmp_path: Path,
    fake_commands: FakeBuildCommands,
) -> None:
    source = inspect_candidate_source(candidate_repository, commands=fake_commands)

    candidate = prepare_candidate(
        _build_request(candidate_repository, tmp_path / "qualification"),
        source=source,
        commands=fake_commands,
    )

    assert candidate.wheel.is_file()
    assert (candidate.wheel.parent / ".gitignore").is_file()
