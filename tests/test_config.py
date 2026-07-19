"""Config loading tests — spec IR-006 (strict validation), §18.2 defaults, OQ-029 discovery.

Traceability (spec: IR-006): unknown keys, wrong types, out-of-range values, and
invalid enum values are each rejected with a clear error; defaults apply when the
file is omitted.
"""

from pathlib import Path

import pytest

from docmend.config import ConfigError, DocmendConfig, load_config


class TestDefaults:
    """Built-in defaults must match the §18.2 reference table exactly."""

    def test_defaults__match_spec_table(self) -> None:
        cfg = DocmendConfig()
        assert cfg.paths.include == ["**/*.txt", "**/*.md", "**/*.html", "**/*.htm"]
        assert "**/.git/**" in cfg.paths.exclude
        assert "**/.venv/**" in cfg.paths.exclude
        assert "**/node_modules/**" in cfg.paths.exclude
        assert cfg.rename.txt_to_md is True
        assert cfg.rename.on_collision == "skip"
        assert cfg.encoding.target == "utf-8"
        assert cfg.encoding.detect is True
        assert cfg.encoding.fail_below_confidence == 0.80
        assert cfg.encoding.non_ascii_floor == 20
        assert cfg.newlines.target == "lf"
        assert cfg.whitespace.trim_trailing is True
        assert cfg.whitespace.ensure_final_newline is True
        assert cfg.whitespace.collapse_blank_lines == 3
        assert cfg.whitespace.normalize_tabs is False
        assert cfg.whitespace.tab_width == 4
        assert cfg.write.dry_run_default is True
        assert cfg.write.backup_dir is None
        assert cfg.write.atomic is True
        assert cfg.limits.per_file_timeout == 60
        assert cfg.limits.max_file_size_mib == 100
        assert cfg.safety.shrink_ratio == 0.50

    def test_no_file_anywhere__yields_defaults(self, tmp_path: Path) -> None:
        assert load_config(cwd=tmp_path) == DocmendConfig()

    def test_empty_toml__yields_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "docmend.toml"
        path.write_text("", encoding="utf-8")
        assert load_config(path) == DocmendConfig()
        assert "parallel" not in DocmendConfig.model_fields

    def test_config_schema__has_no_write_enable_key(self) -> None:
        """OQ-014/OQ-029: config alone can never enable real writes.

        Structural proof: no boolean in the write section can opt into mutation —
        the only write-related toggles make runs MORE conservative.
        """
        write_fields = set(DocmendConfig().write.__class__.model_fields)
        assert write_fields == {"dry_run_default", "backup_dir", "atomic"}


class TestDiscoveryAndPrecedence:
    """OQ-029: explicit path > ./docmend.toml auto-discovery > built-in defaults."""

    def test_autodiscovers_docmend_toml_in_cwd(self, tmp_path: Path) -> None:
        (tmp_path / "docmend.toml").write_text(
            "[whitespace]\ncollapse_blank_lines = 1\n", encoding="utf-8"
        )
        cfg = load_config(cwd=tmp_path)
        assert cfg.whitespace.collapse_blank_lines == 1

    def test_explicit_path_wins_over_autodiscovery(self, tmp_path: Path) -> None:
        (tmp_path / "docmend.toml").write_text(
            "[whitespace]\ncollapse_blank_lines = 1\n", encoding="utf-8"
        )
        explicit = tmp_path / "other.toml"
        explicit.write_text("[whitespace]\ncollapse_blank_lines = 2\n", encoding="utf-8")
        cfg = load_config(explicit, cwd=tmp_path)
        assert cfg.whitespace.collapse_blank_lines == 2

    def test_explicit_missing_path__is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="cannot read"):
            load_config(tmp_path / "absent.toml")

    def test_partial_file__unset_sections_keep_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "docmend.toml"
        path.write_text("[rename]\non_collision = 'fail'\n", encoding="utf-8")
        cfg = load_config(path)
        assert cfg.rename.on_collision == "fail"
        assert cfg.encoding.fail_below_confidence == 0.80  # untouched section intact

    def test_utf8_bom_prefixed_file__loads_same_as_bomless(self, tmp_path: Path) -> None:
        """IR-006: a docmend.toml saved with a UTF-8 BOM (common from Windows/GUI
        editors) is structurally valid TOML and must load identically to the
        BOM-less file, not fail as invalid TOML."""
        body = "[whitespace]\ncollapse_blank_lines = 1\n"
        bom_path = tmp_path / "docmend.toml"
        bom_path.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
        plain_path = tmp_path / "plain.toml"
        plain_path.write_text(body, encoding="utf-8")
        assert load_config(bom_path) == load_config(plain_path)

    def test_write_backup_dir__toml_string_coerces_to_path(self, tmp_path: Path) -> None:
        """§18.2: `write.backup_dir` is a documented TOML key; tomllib only ever
        hands back a str for it, so strict=True must not reject that str
        outright (it would make the key impossible to set from any file)."""
        path = tmp_path / "docmend.toml"
        path.write_text("[write]\nbackup_dir = 'backups'\n", encoding="utf-8")
        cfg = load_config(path)
        assert cfg.write.backup_dir == Path("backups")


class TestStrictValidation:
    """IR-006 acceptance criteria: each rejection class produces a clear error."""

    @staticmethod
    def _load(tmp_path: Path, toml_text: str) -> DocmendConfig:
        path = tmp_path / "docmend.toml"
        path.write_text(toml_text, encoding="utf-8")
        return load_config(path)

    def test_unknown_top_level_key__rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="wite"):
            self._load(tmp_path, "[wite]\ndry_run_default = true\n")

    def test_unknown_nested_key__rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match=r"rename\.txt_to_markdown"):
            self._load(tmp_path, "[rename]\ntxt_to_markdown = true\n")

    def test_wrong_type__rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match=r"encoding\.detect"):
            self._load(tmp_path, "[encoding]\ndetect = 'yes'\n")

    def test_invalid_enum_value__rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match=r"rename\.on_collision"):
            self._load(tmp_path, "[rename]\non_collision = 'prompt'\n")

    @pytest.mark.parametrize(
        "toml_text",
        [
            "[encoding]\nfail_below_confidence = 1.5\n",
            "[encoding]\nnon_ascii_floor = -1\n",
            "[whitespace]\ncollapse_blank_lines = -1\n",
            "[whitespace]\ntab_width = 0\n",
            "[limits]\nper_file_timeout = 0\n",
            "[limits]\nmax_file_size_mib = 0\n",
            "[safety]\nshrink_ratio = 0.0\n",
            "[safety]\nshrink_ratio = 1.5\n",
        ],
    )
    def test_out_of_range_value__rejected(self, tmp_path: Path, toml_text: str) -> None:
        with pytest.raises(ConfigError):
            self._load(tmp_path, toml_text)

    @pytest.mark.parametrize(
        "body",
        [
            "[parallel]\n",
            "[parallel]\nenabled = false\n",
            "[parallel]\nmodel = 'process'\n",
            "[parallel]\nworkers = 'auto'\n",
            "[parallel]\nstart_method = 'forkserver'\n",
            "[parallel]\nchunksize = 'auto'\n",
            "[parallel]\nmaxtasksperchild = 100\n",
        ],
    )
    def test_legacy_parallel_table__migration_error(self, tmp_path: Path, body: str) -> None:
        with pytest.raises(
            ConfigError, match=r"parallel execution never shipped.*remove.*parallel"
        ):
            self._load(tmp_path, body)

    def test_invalid_toml__rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not valid TOML"):
            self._load(tmp_path, "[paths\ninclude = [\n")

    def test_int_for_float_field__accepted(self, tmp_path: Path) -> None:
        """`fail_below_confidence = 1` is honest TOML for 1.0; don't punish it."""
        cfg = self._load(tmp_path, "[encoding]\nfail_below_confidence = 1\n")
        assert cfg.encoding.fail_below_confidence == 1.0
