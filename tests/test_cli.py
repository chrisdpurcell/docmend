"""CLI shell tests — spec IR-005 global flags (MS-0 exit criterion: `docmend --help` works).

Traceability (spec: IR-005): --help/-h, --version/-V, --verbose/-v, --quiet/-q are
live now; --dry-run/-n is accepted and threaded through GlobalOptions, gaining
effect when write-capable commands land (MS-3). The --verbose/--quiet exclusivity
error is asserted here.
"""

from typer.testing import CliRunner

from docmend import __version__
from docmend.cli import app

runner = CliRunner()


class TestHelp:
    def test_bare_invocation__shows_help_and_exits_zero(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_help_flag__exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_short_help_alias(self) -> None:
        result = runner.invoke(app, ["-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output


class TestVersion:
    def test_version_flag__prints_package_version_and_exits_zero(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip() == f"docmend {__version__}"

    def test_short_version_alias(self) -> None:
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestVerbosityFlags:
    def test_verbose_and_quiet_together__usage_error_exit_2(self) -> None:
        """IR-005: the two are mutually exclusive; §18.5 exit 2 = input error."""
        result = runner.invoke(app, ["--verbose", "--quiet"])
        assert result.exit_code == 2
        assert "mutually exclusive" in result.output

    def test_short_flags_conflict__same_error(self) -> None:
        result = runner.invoke(app, ["-v", "-q"])
        assert result.exit_code == 2

    def test_verbose_alone__accepted(self) -> None:
        assert runner.invoke(app, ["-v"]).exit_code == 0

    def test_quiet_alone__accepted(self) -> None:
        assert runner.invoke(app, ["-q"]).exit_code == 0

    def test_repeated_verbose__accepted(self) -> None:
        assert runner.invoke(app, ["-vv"]).exit_code == 0

    def test_dry_run_flag__accepted_globally(self) -> None:
        assert runner.invoke(app, ["--dry-run"]).exit_code == 0
        assert runner.invoke(app, ["-n"]).exit_code == 0
