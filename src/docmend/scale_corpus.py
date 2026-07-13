"""Deterministic streamed corpus generation for DMR-08 qualification.

The recipe stream preserves the historical 40-bucket behavioral mix without
shipping Faker or importing test code. Every traversal owns a newly seeded
``random.Random`` and retains only its current recipe/body, so a one-million-
file run never accumulates document objects or bytes.

Materialization is intentionally stricter than an ordinary fixture writer: the
corpus root must be absent, directories are owner-only, and every file is
created descriptor-relative with exclusive no-follow flags. Published entries
and unpublished private directories from a failed attempt remain for diagnosis.
Pathname cleanup is forbidden because a validated directory name can be
substituted before removal.
"""

import ctypes
import errno
import os
import random
import secrets
import stat
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from docmend.scale_resources import allocated_bytes

MAX_SCALE_FILE_COUNT = 1_000_000
SCALE_CORPUS_SEED = 20_260_713

_BUCKET_COUNT = 40
_FIRST_SHARD_COUNT = 53
_SECOND_SHARD_COUNT = 41
_SHARD_PAIR_COUNT = _FIRST_SHARD_COUNT * _SECOND_SHARD_COUNT
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600
_PRIVATE_DIRECTORY_PREFIX = ".docmend-corpus-"
_RENAME_NOREPLACE = 1

_DIRECTORY_FLAG = cast("int", getattr(os, "O_DIRECTORY", 0))
_NOFOLLOW_FLAG = cast("int", getattr(os, "O_NOFOLLOW", 0))
_CLOEXEC_FLAG = cast("int", getattr(os, "O_CLOEXEC", 0))
_LIBC = ctypes.CDLL(None, use_errno=True)
_RENAMEAT2 = cast(
    "Callable[..., int] | None",
    getattr(_LIBC, "renameat2", None),
)

type RecipeEncoding = Literal["utf-8", "windows-1252"]
type RecipeNewline = Literal["lf", "crlf"]
type FindingKey = tuple[str, Literal["encoding"]]
type DirectoryKey = tuple[str, ...]
type DirectoryIdentity = tuple[int, int]


class ScaleRecipeClass(StrEnum):
    """The six plan dispositions represented by the normative bucket mix."""

    RENAME_ONLY = "rename-only"
    REWRITE_AND_RENAME = "rewrite-and-rename"
    CLEAN_MARKDOWN = "clean-markdown"
    REWRITE_MARKDOWN = "rewrite-markdown"
    LEGACY_CONVERSION = "legacy-conversion"
    BELOW_FLOOR_SKIP = "below-floor-skip"


@dataclass(frozen=True, slots=True)
class ScaleRecipe:
    """Describe one safe relative synthetic file without retaining its body."""

    index: int
    path: str
    recipe_class: ScaleRecipeClass
    encoding: RecipeEncoding
    newline: RecipeNewline
    render_seed: int

    def __post_init__(self) -> None:
        if type(self.index) is not int or not 0 <= self.index < MAX_SCALE_FILE_COUNT:
            raise ValueError("recipe index must be an integer from 0 to 999999")
        if type(self.render_seed) is not int or self.render_seed < 0:
            raise ValueError("render_seed must be a non-negative integer")
        _validate_relative_path(self.path)


@dataclass(frozen=True, slots=True)
class ScaleRecipeCounts:
    """Exact recipe-class cardinalities for one requested corpus count."""

    rename_only: int
    rewrite_and_rename: int
    clean_markdown: int
    rewrite_markdown: int
    legacy_conversion: int
    below_floor_skip: int

    @property
    def actions(self) -> int:
        return (
            self.rename_only
            + self.rewrite_and_rename
            + self.rewrite_markdown
            + self.legacy_conversion
        )

    @property
    def noops(self) -> int:
        return self.clean_markdown

    @property
    def skips(self) -> int:
        return self.below_floor_skip

    @property
    def total(self) -> int:
        return self.actions + self.noops + self.skips


@dataclass(frozen=True, slots=True)
class ScaleCorpusSummary:
    """Return exact logical, physical-allocation, and inode corpus needs."""

    count: int
    file_bytes: int
    allocated_bytes: int
    file_inodes: int
    directory_inodes: int
    recipe_counts: ScaleRecipeCounts

    @property
    def required_inodes(self) -> int:
        return self.file_inodes + self.directory_inodes


def _validate_count(count: int) -> None:
    if type(count) is not int or not 1 <= count <= MAX_SCALE_FILE_COUNT:
        raise ValueError("count must be an integer from 1 to 1000000")


def _validate_relative_path(path: str) -> None:
    if type(path) is not str:
        raise ValueError("recipe path must be a canonical safe relative POSIX path")
    pure = PurePosixPath(path)
    if (
        not path
        or path != pure.as_posix()
        or pure.is_absolute()
        or "\\" in path
        or any(part in ("", ".", "..") for part in pure.parts)
    ):
        raise ValueError("recipe path must be a canonical safe relative POSIX path")


def _partial_bucket_count(remainder: int, start: int, stop: int) -> int:
    return max(0, min(remainder, stop) - start)


def recipe_counts(count: int) -> ScaleRecipeCounts:
    """Return the normative class counts derived from ``count = 40q + r``."""
    _validate_count(count)
    full_cycles, remainder = divmod(count, _BUCKET_COUNT)
    return ScaleRecipeCounts(
        rename_only=24 * full_cycles + _partial_bucket_count(remainder, 0, 24),
        rewrite_and_rename=8 * full_cycles + _partial_bucket_count(remainder, 24, 32),
        clean_markdown=4 * full_cycles + _partial_bucket_count(remainder, 32, 36),
        rewrite_markdown=2 * full_cycles + _partial_bucket_count(remainder, 36, 38),
        legacy_conversion=full_cycles + _partial_bucket_count(remainder, 38, 39),
        below_floor_skip=full_cycles + _partial_bucket_count(remainder, 39, 40),
    )


def corpus_inode_needs(count: int) -> tuple[int, int]:
    """Return file and directory inode needs, including the corpus root."""
    _validate_count(count)
    directories = 2 + min(count, _FIRST_SHARD_COUNT) + min(count, _SHARD_PAIR_COUNT)
    return count, directories


def _class_for_bucket(bucket: int) -> ScaleRecipeClass:
    if bucket < 24:
        return ScaleRecipeClass.RENAME_ONLY
    if bucket < 32:
        return ScaleRecipeClass.REWRITE_AND_RENAME
    if bucket < 36:
        return ScaleRecipeClass.CLEAN_MARKDOWN
    if bucket < 38:
        return ScaleRecipeClass.REWRITE_MARKDOWN
    if bucket == 38:
        return ScaleRecipeClass.LEGACY_CONVERSION
    return ScaleRecipeClass.BELOW_FLOOR_SKIP


def _recipe(index: int, render_seed: int) -> ScaleRecipe:
    recipe_class = _class_for_bucket(index % _BUCKET_COUNT)
    suffix = (
        "md"
        if recipe_class in (ScaleRecipeClass.CLEAN_MARKDOWN, ScaleRecipeClass.REWRITE_MARKDOWN)
        else "txt"
    )
    first_shard = index % _FIRST_SHARD_COUNT
    second_shard = (index // _FIRST_SHARD_COUNT) % _SECOND_SHARD_COUNT
    path = f"lib/{first_shard:02d}/{second_shard:02d}/doc{index:06d}.{suffix}"
    encoding: RecipeEncoding = (
        "windows-1252"
        if recipe_class in (ScaleRecipeClass.LEGACY_CONVERSION, ScaleRecipeClass.BELOW_FLOOR_SKIP)
        else "utf-8"
    )
    newline: RecipeNewline = (
        "crlf"
        if recipe_class
        in (
            ScaleRecipeClass.REWRITE_AND_RENAME,
            ScaleRecipeClass.REWRITE_MARKDOWN,
            ScaleRecipeClass.LEGACY_CONVERSION,
        )
        else "lf"
    )
    return ScaleRecipe(
        index=index,
        path=path,
        recipe_class=recipe_class,
        encoding=encoding,
        newline=newline,
        render_seed=render_seed,
    )


def _iter_recipes(count: int) -> Iterator[ScaleRecipe]:
    # A new generator owns a new RNG. Summary and materialization therefore
    # consume identical random draws without sharing mutable global state.
    randomizer = random.Random(SCALE_CORPUS_SEED)
    for index in range(count):
        yield _recipe(index, randomizer.getrandbits(64))


def iter_recipes(count: int) -> Iterator[ScaleRecipe]:
    """Return a constant-memory iterator of frozen recipes in index order."""
    _validate_count(count)
    return _iter_recipes(count)


_SYNTHETIC_WORDS = (
    "amber",
    "beacon",
    "cedar",
    "delta",
    "ember",
    "forest",
    "garden",
    "harbor",
    "island",
    "jigsaw",
    "kernel",
    "lantern",
    "meadow",
    "nectar",
    "orbit",
    "prairie",
)

# This stable cp1252 prose is intentionally rich in decode-equivalent German
# characters. The installed classifier detects it above 0.80, unlike short
# French/Spanish accent mixes that can receive a confident cp1257 misdecode.
_LEGACY_ABOVE_FLOOR = (
    "Der Wähler äußerte seine Meinung über die Größe der Straße und die Übernahme "
    "der Bäckerei am Übergang, während die Kälte über München hereinbrach. Später "
    "überquerte er die Brücke, müde und übernächtigt, während der Bürgermeister "
    "über die städtische Wärmeversorgung sprach und die Bevölkerung über die höheren "
    "Übertragungsgebühren klagte."
)


def _ascii_body(recipe: ScaleRecipe) -> str:
    randomizer = random.Random(recipe.render_seed)
    words = " ".join(randomizer.choice(_SYNTHETIC_WORDS) for _ in range(12))
    return f"Synthetic document {recipe.index:06d}: {words}."


def render_recipe(recipe: ScaleRecipe) -> bytes:
    """Render one recipe to deterministic, wholly synthetic bytes."""
    match recipe.recipe_class:
        case ScaleRecipeClass.LEGACY_CONVERSION:
            body = f"{_LEGACY_ABOVE_FLOOR} Synthetic record {recipe.index:06d}."
        case ScaleRecipeClass.BELOW_FLOOR_SKIP:
            body = f"Café naïve synthetic record {recipe.index:06d}."
        case _:
            body = _ascii_body(recipe)
    ending = "\r\n" if recipe.newline == "crlf" else "\n"
    text = body + ending
    if recipe.encoding == "windows-1252":
        return text.encode("cp1252")
    return text.encode("utf-8")


def summarize_scale_corpus(count: int, *, fragment_size: int) -> ScaleCorpusSummary:
    """Compute the exact no-write corpus budget with per-file block rounding."""
    counts = recipe_counts(count)
    allocated_bytes(0, fragment_size)
    logical_total = 0
    allocated_total = 0
    for recipe in iter_recipes(count):
        size = len(render_recipe(recipe))
        logical_total += size
        allocated_total += allocated_bytes(size, fragment_size)
    file_inodes, directory_inodes = corpus_inode_needs(count)
    return ScaleCorpusSummary(
        count=count,
        file_bytes=logical_total,
        allocated_bytes=allocated_total,
        file_inodes=file_inodes,
        directory_inodes=directory_inodes,
        recipe_counts=counts,
    )


def boundary_samples(count: int) -> tuple[ScaleRecipe, ...]:
    """Select the first and last recipe of every class present in the corpus."""
    _validate_count(count)
    first: dict[ScaleRecipeClass, ScaleRecipe] = {}
    last: dict[ScaleRecipeClass, ScaleRecipe] = {}
    for recipe in iter_recipes(count):
        first.setdefault(recipe.recipe_class, recipe)
        last[recipe.recipe_class] = recipe
    indexes = {
        recipe.index: recipe
        for recipe_class in ScaleRecipeClass
        for recipe in (first.get(recipe_class), last.get(recipe_class))
        if recipe is not None
    }
    return tuple(indexes[index] for index in sorted(indexes))


def expected_finding_keys(count: int) -> tuple[FindingKey, ...]:
    """Return the sorted verification multiset for intentional plan skips."""
    findings: list[FindingKey] = [
        (recipe.path, "encoding")
        for recipe in iter_recipes(count)
        if recipe.recipe_class is ScaleRecipeClass.BELOW_FLOOR_SKIP
    ]
    findings.sort()
    return tuple(findings)


def _open_directory(path: Path) -> int:
    if not _DIRECTORY_FLAG or not _NOFOLLOW_FLAG:
        raise OSError("scale corpus materialization requires directory no-follow support")
    return os.open(
        path,
        os.O_RDONLY | _DIRECTORY_FLAG | _NOFOLLOW_FLAG | _CLOEXEC_FLAG,
    )


def _directory_label(key: DirectoryKey) -> str:
    return PurePosixPath(*key).as_posix()


def _validated_directory_identity(
    details: os.stat_result,
    key: DirectoryKey,
) -> DirectoryIdentity:
    label = _directory_label(key)
    if not stat.S_ISDIR(details.st_mode):
        raise OSError(f"corpus path is not a directory: {label}")
    if stat.S_IMODE(details.st_mode) & ~_DIRECTORY_MODE:
        raise OSError(f"corpus directory is not owner-only: {label}")
    return details.st_dev, details.st_ino


def _directory_identity(fd: int, key: DirectoryKey) -> DirectoryIdentity:
    return _validated_directory_identity(os.fstat(fd), key)


def _directory_name_identity(
    parent_fd: int,
    name: str,
    key: DirectoryKey,
) -> DirectoryIdentity:
    details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    return _validated_directory_identity(details, key)


def _require_directory_name_identity(
    parent_fd: int,
    name: str,
    key: DirectoryKey,
    expected: DirectoryIdentity,
) -> None:
    if _directory_name_identity(parent_fd, name, key) != expected:
        raise OSError(f"corpus directory identity changed: {_directory_label(key)}")


def _rename_noreplace(parent_fd: int, source: str, destination: str) -> None:
    if _RENAMEAT2 is None:
        raise OSError(errno.ENOSYS, "renameat2 is required for scale corpus materialization")
    result = _RENAMEAT2(
        ctypes.c_int(parent_fd),
        ctypes.c_char_p(os.fsencode(source)),
        ctypes.c_int(parent_fd),
        ctypes.c_char_p(os.fsencode(destination)),
        ctypes.c_uint(_RENAME_NOREPLACE),
    )
    if result != 0:
        error_number = ctypes.get_errno() or errno.EIO
        raise OSError(error_number, os.strerror(error_number), destination)


def _private_directory_name() -> str:
    return f"{_PRIVATE_DIRECTORY_PREFIX}{secrets.token_hex(16)}"


def _directory_is_empty(directory_fd: int) -> bool:
    # pathlib cannot preserve descriptor binding for this emptiness check.
    return not os.listdir(directory_fd)


def _create_published_directory(
    parent_fd: int,
    name: str,
    key: DirectoryKey,
    *,
    collision_message: str,
) -> tuple[int, DirectoryIdentity]:
    private_name = _private_directory_name()
    try:
        os.mkdir(private_name, mode=_DIRECTORY_MODE, dir_fd=parent_fd)
    except FileExistsError as exc:
        raise OSError("could not reserve a private corpus directory") from exc

    directory_fd: int | None = None
    identity: DirectoryIdentity | None = None
    try:
        directory_fd = os.open(
            private_name,
            os.O_RDONLY | _DIRECTORY_FLAG | _NOFOLLOW_FLAG | _CLOEXEC_FLAG,
            dir_fd=parent_fd,
        )
        details = os.fstat(directory_fd)
        identity = (details.st_dev, details.st_ino)
        _validated_directory_identity(details, key)
        if not _directory_is_empty(directory_fd):
            raise OSError(f"private corpus directory is not empty: {_directory_label(key)}")
        _require_directory_name_identity(parent_fd, private_name, key, identity)
        try:
            _rename_noreplace(parent_fd, private_name, name)
        except FileExistsError as exc:
            raise FileExistsError(collision_message) from exc
        _require_directory_name_identity(parent_fd, name, key, identity)
        if not _directory_is_empty(directory_fd):
            raise OSError(f"published corpus directory is not empty: {_directory_label(key)}")
    except BaseException:
        if directory_fd is not None:
            # A stat-then-rmdir cleanup can delete an unknown empty directory
            # substituted after the identity check. Preserve failure residue.
            os.close(directory_fd)
        raise
    return directory_fd, identity


def _open_known_directory(
    parent_fd: int,
    name: str,
    key: DirectoryKey,
    expected: DirectoryIdentity,
) -> int:
    directory_fd = os.open(
        name,
        os.O_RDONLY | _DIRECTORY_FLAG | _NOFOLLOW_FLAG | _CLOEXEC_FLAG,
        dir_fd=parent_fd,
    )
    try:
        if _directory_identity(directory_fd, key) != expected:
            raise OSError(f"corpus directory identity changed: {_directory_label(key)}")
        _require_directory_name_identity(parent_fd, name, key, expected)
    except BaseException:
        os.close(directory_fd)
        raise
    return directory_fd


def _open_child_directory(
    parent_fd: int,
    name: str,
    key: DirectoryKey,
    identities: dict[DirectoryKey, DirectoryIdentity],
) -> int:
    known_identity = identities.get(key)
    if known_identity is not None:
        return _open_known_directory(parent_fd, name, key, known_identity)

    directory_fd, identity = _create_published_directory(
        parent_fd,
        name,
        key,
        collision_message=f"unexpected corpus directory collision: {_directory_label(key)}",
    )
    identities[key] = identity
    return directory_fd


def _validate_directory_names(
    root_fd: int,
    identities: dict[DirectoryKey, DirectoryIdentity],
) -> None:
    """Reopen every published directory name from the held corpus root."""
    for key in sorted(identities, key=lambda value: (len(value), value)):
        if not key:
            continue
        current_fd = os.dup(root_fd)
        try:
            for depth, name in enumerate(key, start=1):
                prefix = key[:depth]
                child_fd = _open_known_directory(
                    current_fd,
                    name,
                    prefix,
                    identities[prefix],
                )
                os.close(current_fd)
                current_fd = child_fd
        finally:
            os.close(current_fd)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("exclusive corpus file write made no progress")
        offset += written


def _materialize_recipe(
    root_fd: int,
    recipe: ScaleRecipe,
    data: bytes,
    directory_identities: dict[DirectoryKey, DirectoryIdentity],
) -> None:
    parts = PurePosixPath(recipe.path).parts
    current_fd = os.dup(root_fd)
    try:
        for depth, directory in enumerate(parts[:-1], start=1):
            key = parts[:depth]
            child_fd = _open_child_directory(
                current_fd,
                directory,
                key,
                directory_identities,
            )
            os.close(current_fd)
            current_fd = child_fd
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW_FLAG | _CLOEXEC_FLAG
        try:
            file_fd = os.open(parts[-1], flags, _FILE_MODE, dir_fd=current_fd)
        except FileExistsError as exc:
            raise FileExistsError(f"corpus path collision: {recipe.path}") from exc
        try:
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                raise OSError(f"corpus path is not a regular file: {recipe.path}")
            _write_all(file_fd, data)
        finally:
            os.close(file_fd)
    finally:
        os.close(current_fd)


def materialize_scale_corpus(
    root: Path,
    count: int,
    *,
    fragment_size: int | None = None,
) -> ScaleCorpusSummary:
    """Publish an absent corpus root and stream an exclusive materialization.

    When omitted, ``fragment_size`` comes from the existing parent filesystem;
    callers can still pass the preflight-observed value to bind both passes to
    the same capacity observation. Directory names are published with Linux
    ``renameat2(RENAME_NOREPLACE)`` after descriptor-bound validation.
    """
    _validate_count(count)
    if root.name in ("", ".", ".."):
        raise ValueError("corpus root must name one new directory")

    parent_fd = _open_directory(root.parent)
    try:
        effective_fragment_size = (
            os.fstatvfs(parent_fd).f_frsize if fragment_size is None else fragment_size
        )
        allocated_bytes(0, effective_fragment_size)
        root_fd, root_identity = _create_published_directory(
            parent_fd,
            root.name,
            (),
            collision_message="corpus root must not already exist",
        )
        try:
            # The set is bounded by the root plus the fixed shard topology
            # (2,228 entries at one million files). Every reuse is opened by
            # name and reconciled to the identity recorded at publication.
            directory_identities: dict[DirectoryKey, DirectoryIdentity] = {(): root_identity}
            logical_total = 0
            allocated_total = 0
            for recipe in iter_recipes(count):
                data = render_recipe(recipe)
                _materialize_recipe(root_fd, recipe, data, directory_identities)
                size = len(data)
                logical_total += size
                allocated_total += allocated_bytes(size, effective_fragment_size)
            _validate_directory_names(root_fd, directory_identities)
            _require_directory_name_identity(
                parent_fd,
                root.name,
                (),
                root_identity,
            )
        finally:
            os.close(root_fd)
    finally:
        os.close(parent_fd)

    file_inodes, directory_inodes = corpus_inode_needs(count)
    return ScaleCorpusSummary(
        count=count,
        file_bytes=logical_total,
        allocated_bytes=allocated_total,
        file_inodes=file_inodes,
        directory_inodes=directory_inodes,
        recipe_counts=recipe_counts(count),
    )
