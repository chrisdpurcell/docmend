"""TOML configuration loading — the §18.2 reference table as strict pydantic models.

Cross-file contract (spec IR-006, D-005, OQ-021, OQ-029):
- stdlib ``tomllib`` parses; pydantic v2 strict models (``extra='forbid'``) validate.
  Unknown keys, wrong types, out-of-range values, and invalid enum values are each
  rejected with a clear error (IR-006) — surfaced as :class:`ConfigError`, which the
  CLI maps to exit 2 (input error, §18.5 taxonomy).
- Precedence is CLI flags > config file > built-in defaults (OQ-029). This module
  owns the file/defaults half; flag overlay lives with the commands (MS-1+) because
  scalar flags override single keys while list flags replace whole lists.
- ``./docmend.toml`` is auto-discovered when no explicit path is given; a missing
  auto-discovered file silently yields built-in defaults, but a missing *explicit*
  path is an error (the user asked for a file that is not there).
- Deliberately no "enable writes" key exists anywhere in this schema: config alone
  can never opt into real mutation — ``apply --write`` is the only opt-in (OQ-014).
  ``write.dry_run_default`` can only make a run *more* conservative, never less.
"""

import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

type PositiveIntOrAuto = Literal["auto"] | Annotated[int, Field(ge=1)]


class ConfigError(Exception):
    """A configuration file could not be read or failed validation (exit 2, §18.5)."""


class _StrictModel(BaseModel):
    # strict=True keeps TOML's own typing honest (no "1" -> 1, no 1 -> True);
    # pydantic strict mode still accepts int for float fields, so
    # `fail_below_confidence = 1` in TOML remains valid.
    model_config = ConfigDict(extra="forbid", strict=True)


class PathsConfig(_StrictModel):
    """§18.2 `paths.*` — markup globs included per OQ-025 (mechanical scope only)."""

    include: list[str] = Field(
        default=["**/*.txt", "**/*.md", "**/*.html", "**/*.htm"],
    )
    # §18.2 names ".git/, .venv/, node_modules/, binary/media patterns" without
    # enumerating the media set; this concrete default realizes that intent.
    # Directory excludes use "**/name/**" so nested occurrences are caught too.
    exclude: list[str] = Field(
        default=[
            "**/.git/**",
            "**/.venv/**",
            "**/node_modules/**",
            # binary/media extension patterns — never candidate documents
            "**/*.png",
            "**/*.jpg",
            "**/*.jpeg",
            "**/*.gif",
            "**/*.bmp",
            "**/*.webp",
            "**/*.ico",
            "**/*.pdf",
            "**/*.zip",
            "**/*.tar",
            "**/*.gz",
            "**/*.bz2",
            "**/*.xz",
            "**/*.7z",
            "**/*.rar",
            "**/*.mp3",
            "**/*.mp4",
            "**/*.avi",
            "**/*.mkv",
            "**/*.mov",
            "**/*.exe",
            "**/*.dll",
            "**/*.so",
            "**/*.woff",
            "**/*.woff2",
            "**/*.ttf",
            "**/*.eot",
        ],
    )


class RenameConfig(_StrictModel):
    """§18.2 `rename.*` — FR-010 extension rename and FR-011 collision policy."""

    txt_to_md: bool = True
    on_collision: Literal["skip", "fail", "overwrite"] = "skip"


class EncodingConfig(_StrictModel):
    """§18.2 `encoding.*` — FR-007 dual skip-gate thresholds (OQ-015)."""

    # Only UTF-8 output exists in v1 (D-002); Literal keeps a future second value
    # an explicit schema change rather than a silent pass-through.
    target: Literal["utf-8"] = "utf-8"
    detect: bool = True
    fail_below_confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.80
    non_ascii_floor: Annotated[int, Field(ge=0)] = 20


class NewlinesConfig(_StrictModel):
    """§18.2 `newlines.*` — FR-008; LF is the only v1 target (D-002)."""

    target: Literal["lf"] = "lf"


class WhitespaceConfig(_StrictModel):
    """§18.2 `whitespace.*` — FR-009 mechanical transforms (OQ-031 tab semantics)."""

    trim_trailing: bool = True
    ensure_final_newline: bool = True
    collapse_blank_lines: Annotated[int, Field(ge=0)] = 3
    normalize_tabs: bool = False
    tab_width: Annotated[int, Field(ge=1)] = 4


class WriteConfig(_StrictModel):
    """§18.2 `write.*` — NFR-002/NFR-004; no key here can enable real writes."""

    dry_run_default: bool = True
    backup_dir: Path | None = None
    atomic: bool = True


class ParallelConfig(_StrictModel):
    """§18.2 `parallel.*` — OQ-016/OQ-027; sequential by default until MS-5 profiling."""

    enabled: bool = False
    model: Literal["process", "sequential"] = "process"
    workers: PositiveIntOrAuto = "auto"
    start_method: Literal["forkserver", "spawn"] = "forkserver"
    chunksize: PositiveIntOrAuto = "auto"
    maxtasksperchild: Annotated[int, Field(ge=1)] | None = None

    @field_validator("model", mode="before")
    @classmethod
    def _reject_reserved_models(cls, value: object) -> object:
        # §18.2: "thread" (free-threaded build) and "interpreter" (PEP 734) are
        # reserved names, distinguished from typos by this dedicated message
        # until the OQ-016 re-open checklist fires.
        if value in ("thread", "interpreter"):
            msg = f"parallel.model {value!r} is reserved and not supported in this release"
            raise ValueError(msg)
        return value


class LimitsConfig(_StrictModel):
    """§18.2 `limits.*` — FR-019 watchdog and plan-time size guard (OQ-028)."""

    per_file_timeout: Annotated[float, Field(gt=0)] = 60
    max_file_size_mib: Annotated[int, Field(ge=1)] = 100


class SafetyConfig(_StrictModel):
    """§18.2 `safety.*` — OQ-030 forward-looking shrink ratio.

    v1's hard invariant (mechanical transforms never reduce non-whitespace
    character count, EC-005) is deliberately NOT configurable and so has no
    key here; this ratio only bounds future content-touching transforms.
    """

    shrink_ratio: Annotated[float, Field(gt=0.0, le=1.0)] = 0.50


class DocmendConfig(_StrictModel):
    """The complete §18.2 configuration surface with built-in defaults."""

    paths: PathsConfig = Field(default_factory=PathsConfig)
    rename: RenameConfig = Field(default_factory=RenameConfig)
    encoding: EncodingConfig = Field(default_factory=EncodingConfig)
    newlines: NewlinesConfig = Field(default_factory=NewlinesConfig)
    whitespace: WhitespaceConfig = Field(default_factory=WhitespaceConfig)
    write: WriteConfig = Field(default_factory=WriteConfig)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)


DEFAULT_CONFIG_FILENAME = "docmend.toml"


def _format_validation_error(path_label: str, exc: ValidationError) -> str:
    findings = "; ".join(
        f"{'.'.join(str(part) for part in err['loc']) or '(top level)'}: {err['msg']}"
        for err in exc.errors()
    )
    return f"{path_label}: invalid configuration — {findings}"


def load_config(path: Path | None = None, *, cwd: Path | None = None) -> DocmendConfig:
    """Load configuration per the OQ-029 discovery rule.

    Explicit ``path`` wins; otherwise ``./docmend.toml`` (relative to ``cwd``,
    defaulting to the process working directory) is auto-discovered; absent
    that, built-in §18.2 defaults apply. Raises :class:`ConfigError` for an
    unreadable/unparseable file or any validation failure.
    """
    if path is None:
        candidate = (cwd or Path.cwd()) / DEFAULT_CONFIG_FILENAME
        if not candidate.is_file():
            return DocmendConfig()
        path = candidate

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"{path}: cannot read configuration file ({exc.strerror or exc})"
        raise ConfigError(msg) from exc
    except tomllib.TOMLDecodeError as exc:
        msg = f"{path}: not valid TOML — {exc}"
        raise ConfigError(msg) from exc

    try:
        return DocmendConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(str(path), exc)) from exc
