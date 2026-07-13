"""Reconcile one DMR-08 scan/plan/apply/verify pipeline end to end.

Artifact paths enter through a private workspace contract.  Public evidence
receives only reduced counts, run identifiers, and byte sizes.  Every direct
reader is bracketed by an exact regular-file snapshot; once a strict read has
succeeded, any later disagreement is a qualification failure rather than an
ambiguous retry.
"""

import fcntl
import hashlib
import json
import math
import os
import stat
from collections import Counter
from collections.abc import Callable, Generator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version as metadata_version
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal, cast

from docmend import __version__
from docmend.artifacts import (
    ArtifactError,
    read_inventory,
    read_plan_snapshot,
    read_report_snapshot,
    read_verify_report,
)
from docmend.config import DocmendConfig
from docmend.inventory import Inventory
from docmend.plan import Plan, PlanAction
from docmend.report import Report
from docmend.scale_corpus import (
    FindingKey,
    ScaleRecipeClass,
    boundary_samples,
    expected_boundary_output,
    expected_finding_keys,
    iter_recipes,
    recipe_counts,
    render_recipe,
)
from docmend.verify_coverage import check_plan_coverage, load_verification_evidence
from docmend.verify_report import VerifyReport
from docmend.writer.manifest import ManifestChain, read_manifest_chain, reduce_lifecycle

type StageName = str
type PublicPipelineFailure = Literal["conservation-mismatch", "finding-mismatch"]
_STRUCTURED_LOG_LEVELS = frozenset(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))


class QualificationIncomplete(Exception):
    """A required pipeline artifact was absent, unreadable, or invalid."""


class QualificationFailure(Exception):
    """Valid pipeline facts disagreed with the qualification contract."""


@dataclass(frozen=True, slots=True)
class PipelinePaths:
    """Private absolute locations of one four-stage pipeline."""

    pipeline: Path
    corpus: Path
    inventory: Path
    plan: Path
    report: Path
    verify_report: Path


@dataclass(frozen=True, slots=True)
class PipelineReconciliation:
    """Phase totals and identifier-free artifact accounting for evidence."""

    count: int
    scanned_files: int
    planned_actions: int
    plan_skips: int
    plan_noops: int
    applied_actions: int
    verified_actions: int
    stage_run_ids: Mapping[StageName, str]
    artifact_bytes: Mapping[str, int]
    structured_log_bytes: Mapping[StageName, int]
    expected_findings: Mapping[FindingKey, int]
    observed_findings: Mapping[FindingKey, int]
    manifest_path: Path
    public_failure: PublicPipelineFailure | None


@dataclass(frozen=True, slots=True)
class PipelinePrefixReconciliation:
    """Current-stage facts derived from the same trusted artifact snapshots."""

    stage: str
    run_id: str
    artifact_bytes: Mapping[str, int]
    scanned_files: int = 0
    planned_actions: int = 0
    plan_skips: int = 0
    plan_noops: int = 0
    applied_actions: int = 0
    apply_skips: int = 0
    failures: int = 0
    not_attempted: int = 0
    verified_actions: int = 0
    observed_findings: int = 0
    public_failure: PublicPipelineFailure | None = None


@dataclass(frozen=True, slots=True)
class _FileSnapshot:
    path: Path
    data: bytes
    device: int
    inode: int
    mode: int
    mtime_ns: int

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def sha256(self) -> str:
        return f"sha256:{hashlib.sha256(self.data).hexdigest()}"


def _snapshot(path: Path, *, kind: str) -> _FileSnapshot:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise QualificationIncomplete(f"{kind} artifact is missing or unreadable") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise QualificationIncomplete(f"{kind} artifact must be a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    return _FileSnapshot(
        path=path,
        data=b"".join(chunks),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
        mtime_ns=metadata.st_mtime_ns,
    )


def _require_unchanged(snapshot: _FileSnapshot, *, kind: str) -> None:
    try:
        current = _snapshot(snapshot.path, kind=kind)
    except QualificationIncomplete as exc:
        raise QualificationIncomplete(f"{kind} artifact changed after its valid read") from exc
    if (
        current.data != snapshot.data
        or current.device != snapshot.device
        or current.inode != snapshot.inode
        or current.mode != snapshot.mode
        or current.mtime_ns != snapshot.mtime_ns
    ):
        raise QualificationIncomplete(f"{kind} artifact changed after its valid read")


@contextmanager
def _captured_path(snapshot: _FileSnapshot) -> Generator[Path]:
    """Expose sealed captured bytes to path-only owner readers."""

    descriptor = os.memfd_create(
        "docmend-qualification-artifact",
        os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
    )
    try:
        remaining = memoryview(snapshot.data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written == 0:
                raise OSError("captured artifact write made no progress")
            remaining = remaining[written:]
        os.fchmod(descriptor, 0o400)
        fcntl.fcntl(
            descriptor,
            fcntl.F_ADD_SEALS,
            fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE,
        )
        yield Path(f"/proc/self/fd/{descriptor}")
    finally:
        os.close(descriptor)


def _direct_read[T](
    snapshot: _FileSnapshot,
    reader: Callable[[Path], T],
    *,
    kind: str,
) -> T:
    try:
        with _captured_path(snapshot) as captured:
            return reader(captured)
    except (ArtifactError, OSError, ValueError) as exc:
        raise QualificationIncomplete(f"{kind} artifact failed strict validation: {exc}") from exc


def _absolute_paths(paths: PipelinePaths) -> PipelinePaths:
    values = {
        "pipeline": paths.pipeline,
        "corpus": paths.corpus,
        "inventory": paths.inventory,
        "plan": paths.plan,
        "report": paths.report,
        "verify_report": paths.verify_report,
    }
    if any(not path.is_absolute() for path in values.values()):
        raise QualificationIncomplete("pipeline reconciliation paths must be absolute")
    return PipelinePaths(**values)


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationFailure(message)


def _require_identity(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationIncomplete(message)


def _select_public_failure(
    *failures: PublicPipelineFailure | None,
) -> PublicPipelineFailure | None:
    if "conservation-mismatch" in failures:
        return "conservation-mismatch"
    if "finding-mismatch" in failures:
        return "finding-mismatch"
    return None


def _observed_plan_noops(plan: Plan, *, count: int) -> int:
    dispositions = {action.path for action in plan.actions} | {
        decision.path for decision in plan.skips
    }
    return sum(
        recipe.recipe_class is ScaleRecipeClass.CLEAN_MARKDOWN and recipe.path not in dispositions
        for recipe in iter_recipes(count)
    )


def _inventory_identity_contract(inventory: Inventory, *, paths: PipelinePaths) -> None:
    default_config = DocmendConfig()
    _require_identity(
        inventory.requested_path == str(paths.corpus)
        and inventory.source_root == str(paths.corpus),
        "inventory root binding disagrees with the qualification corpus",
    )
    _require_identity(
        inventory.generated_by == f"docmend {__version__}",
        "inventory producer version disagrees with the candidate",
    )
    _require_identity(
        inventory.scan_config.include == default_config.paths.include
        and inventory.scan_config.exclude == default_config.paths.exclude
        and inventory.scan_config.encoding_detect is True
        and inventory.scan_config.detector
        == f"charset-normalizer {metadata_version('charset-normalizer')}",
        "inventory scan config disagrees with the exact qualification defaults",
    )
    _require_identity(
        len({record.path for record in inventory.files}) == len(inventory.files),
        "inventory contains duplicate paths",
    )


def _plan_identity_contract(
    plan: Plan,
    *,
    inventory: Inventory,
    inventory_sha256: str,
    paths: PipelinePaths,
) -> None:
    _require_identity(
        plan.source_root == str(paths.corpus), "plan source root disagrees with corpus"
    )
    _require_identity(
        plan.generated_by == f"docmend {__version__}",
        "plan producer version disagrees with the candidate",
    )
    _require_identity(
        plan.config == DocmendConfig().model_dump(mode="json"),
        "plan config is not the qualification default",
    )
    _require_identity(
        plan.inventory_ref.path == str(paths.inventory)
        and plan.inventory_ref.run_id == inventory.run_id
        and plan.inventory_ref.sha256 == inventory_sha256,
        "plan inventory binding disagrees with the validated snapshot",
    )
    action_ids = [action.action_id for action in plan.actions]
    action_paths = [action.path for action in plan.actions]
    skip_paths = [skip.path for skip in plan.skips]
    _require_identity(len(set(action_ids)) == len(action_ids), "plan contains duplicate action IDs")
    _require_identity(
        len(set(action_paths)) == len(action_paths), "plan contains duplicate action paths"
    )
    _require_identity(
        len({action.docmend_id for action in plan.actions}) == len(plan.actions),
        "plan contains duplicate document IDs",
    )
    _require_identity(len(set(skip_paths)) == len(skip_paths), "plan contains duplicate skip paths")
    _require_identity(
        all(action.action_id.startswith(f"{plan.run_id}/a") for action in plan.actions),
        "plan action ID provenance disagrees with the plan run",
    )


def _report_identity_contract(
    report: Report,
    *,
    plan: Plan,
    plan_sha256: str,
    paths: PipelinePaths,
) -> None:
    _require_identity(
        report.generated_by == f"docmend {__version__}",
        "report producer version disagrees with the candidate",
    )
    outcome_ids = [outcome.action_id for outcome in report.outcomes]
    _require_identity(
        len(set(outcome_ids)) == len(outcome_ids), "report contains duplicate outcomes"
    )
    _require_identity(
        report.plan_ref.path == str(paths.plan)
        and report.plan_ref.run_id == plan.run_id
        and report.plan_ref.sha256 == plan_sha256,
        "report plan binding disagrees with the validated snapshot",
    )
    _require_identity(report.prior_attempt is None, "report unexpectedly names a prior attempt")
    _require_identity(report.manifest_sha256 is not None, "report omits its manifest hash")
    actions = {action.action_id: action for action in plan.actions}
    for outcome in report.outcomes:
        action = actions.get(outcome.action_id)
        if action is None:
            continue
        _require_identity(
            outcome.path == action.path and outcome.before_sha256 == action.source_sha256,
            f"report outcome binding disagrees for {action.path}",
        )


def _manifest_identity_contract(
    chain: ManifestChain,
    snapshot: _FileSnapshot,
    *,
    report: Report,
    plan: Plan,
    plan_sha256: str,
    paths: PipelinePaths,
) -> None:
    _require_identity(snapshot.data.endswith(b"\n"), "manifest lacks its terminal newline")
    _require_identity(all(snapshot.data.splitlines()), "manifest contains an empty NDJSON record")
    _require_identity(
        report.manifest_sha256 == snapshot.sha256,
        "report manifest binding disagrees with validated bytes",
    )
    actions = {action.action_id: action for action in plan.actions}
    outcomes = {outcome.action_id: outcome for outcome in report.outcomes}
    for manifest_set in chain.sets:
        header = manifest_set.header
        _require_identity(
            header.kind == "apply"
            and header.run_id == report.run_id
            and header.source_root == str(paths.corpus)
            and header.plan_sha256 == plan_sha256
            and header.prior_manifest_sha256 is None
            and header.prior_attempt is None,
            "manifest header binding disagrees with plan/report/corpus",
        )
        _require_identity(
            header.effective_excludes == tuple(DocmendConfig().paths.exclude),
            "manifest header binding disagrees with exact default excludes",
        )
        _require_identity(
            manifest_set.sha256 == snapshot.sha256,
            "manifest set hash disagrees with validated bytes",
        )
        for record in manifest_set.records:
            action = actions.get(record.action_id)
            outcome = outcomes.get(record.action_id)
            _require_identity(
                action is not None,
                f"manifest record names an unidentified action {record.action_id}",
            )
            assert action is not None
            target_relative = action.target_path if action.target_path is not None else action.path
            _require_identity(
                record.run_id == report.run_id
                and record.docmend_id == action.docmend_id
                and record.original_path == str(paths.corpus / action.path)
                and record.target_path == str(paths.corpus / target_relative)
                and record.before_sha256 == action.source_sha256
                and (outcome is None or record.after_sha256 == outcome.after_sha256),
                f"manifest record binding disagrees for {action.action_id}",
            )
            _require_identity(
                record.source_identity is not None
                and record.expected_published_identity is not None,
                f"manifest record omits required object identity for {action.action_id}",
            )


def _inventory_contract(
    inventory: Inventory,
    *,
    count: int,
    paths: PipelinePaths,
    allow_public_mismatch: bool = False,
) -> PublicPipelineFailure | None:
    records = {record.path: record for record in inventory.files}
    default_config = DocmendConfig()
    _require(
        inventory.requested_path == str(paths.corpus)
        and inventory.source_root == str(paths.corpus),
        "inventory root binding disagrees with the qualification corpus",
    )
    _require(
        inventory.generated_by == f"docmend {__version__}",
        "inventory producer version disagrees with the candidate",
    )
    _require(
        inventory.scan_config.include == default_config.paths.include
        and inventory.scan_config.exclude == default_config.paths.exclude
        and inventory.scan_config.encoding_detect is True
        and inventory.scan_config.detector
        == f"charset-normalizer {metadata_version('charset-normalizer')}",
        "inventory scan config disagrees with the exact qualification defaults",
    )
    _require(len(records) == len(inventory.files), "inventory contains duplicate paths")
    _require(len(records) == count, "inventory path set disagrees with corpus recipes")
    file_count_mismatch = inventory.totals.files != count
    if not allow_public_mismatch:
        _require(not file_count_mismatch, "inventory file count disagrees with corpus")
    _require(not inventory.symlinks and inventory.totals.symlinks == 0, "inventory found symlinks")
    _require(not inventory.skipped and inventory.totals.skipped == 0, "inventory skipped files")
    _require(
        inventory.totals.skipped_by_reason.excluded == 0
        and inventory.totals.skipped_by_reason.unreadable == 0
        and inventory.totals.skipped_by_reason.timeout == 0,
        "inventory skip totals are nonzero",
    )
    _require(
        not inventory.hard_link_groups and inventory.totals.hard_link_groups == 0,
        "inventory found hard-link groups",
    )
    logical_bytes = 0
    for recipe in iter_recipes(count):
        data = render_recipe(recipe)
        logical_bytes += len(data)
        record = records.get(recipe.path)
        _require(record is not None, "inventory path set disagrees with corpus recipes")
        assert record is not None
        expected_newline = recipe.newline
        non_ascii = sum(byte >= 0x80 for byte in data)
        utf8_valid = True
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            utf8_valid = False
        _require(record.size_bytes == len(data), f"inventory size disagrees for {recipe.path}")
        _require(record.sha256 == _sha256(data), f"inventory hash disagrees for {recipe.path}")
        _require(
            record.suffix == PurePosixPath(recipe.path).suffix,
            f"inventory suffix disagrees for {recipe.path}",
        )
        _require(record.nlink == 1, f"inventory link count disagrees for {recipe.path}")
        _require(
            record.newline_style == expected_newline,
            f"inventory newline disagrees for {recipe.path}",
        )
        _require(not record.nul_bytes, f"inventory NUL verdict disagrees for {recipe.path}")
        _require(
            record.non_ascii_bytes == non_ascii,
            f"inventory non-ASCII count disagrees for {recipe.path}",
        )
        _require(record.encoding.bom is None, f"inventory BOM disagrees for {recipe.path}")
        _require(
            record.encoding.utf8_valid is utf8_valid,
            f"inventory UTF-8 verdict disagrees for {recipe.path}",
        )
        _require(
            record.encoding.ascii_only is (non_ascii == 0),
            f"inventory ASCII verdict disagrees for {recipe.path}",
        )
        detected = record.encoding.detected
        _require(detected is not None, f"inventory encoding provenance missing for {recipe.path}")
        assert detected is not None
        if recipe.encoding == "utf-8":
            _require(
                detected.name == "utf-8"
                and detected.method == "utf8-strict"
                and detected.confidence == 1.0,
                f"inventory UTF-8 provenance disagrees for {recipe.path}",
            )
        else:
            _require(
                not utf8_valid
                and detected.method == "charset-normalizer"
                and detected.confidence >= DocmendConfig().encoding.fail_below_confidence,
                f"inventory legacy detection threshold/provenance disagrees for {recipe.path}",
            )
    _require(
        inventory.totals.total_size_bytes == logical_bytes,
        "inventory total bytes disagree with corpus recipes",
    )
    return "conservation-mismatch" if file_count_mismatch else None


_EXPECTED_OPERATIONS: Mapping[ScaleRecipeClass, tuple[str, ...]] = MappingProxyType(
    {
        ScaleRecipeClass.RENAME_ONLY: ("rename",),
        ScaleRecipeClass.REWRITE_AND_RENAME: ("normalize_newlines", "rename"),
        ScaleRecipeClass.REWRITE_MARKDOWN: ("normalize_newlines",),
        ScaleRecipeClass.LEGACY_CONVERSION: ("reencode", "normalize_newlines", "rename"),
    }
)


def _plan_contract(
    plan: Plan,
    *,
    inventory: Inventory,
    inventory_sha256: str,
    paths: PipelinePaths,
    count: int,
    allow_public_mismatch: bool = False,
) -> tuple[dict[str, PlanAction], PublicPipelineFailure | None]:
    counts = recipe_counts(count)
    _require(plan.source_root == str(paths.corpus), "plan source root disagrees with corpus")
    _require(
        plan.generated_by == f"docmend {__version__}",
        "plan producer version disagrees with the candidate",
    )
    expected_config = DocmendConfig().model_dump(mode="json")
    _require(plan.config == expected_config, "plan config is not the qualification default")
    _require(
        plan.inventory_ref.path == str(paths.inventory)
        and plan.inventory_ref.run_id == inventory.run_id
        and plan.inventory_ref.sha256 == inventory_sha256,
        "plan inventory binding disagrees with the validated snapshot",
    )
    _require(len(plan.actions) == counts.actions, "plan action set disagrees with recipe partition")
    _require(len(plan.skips) == counts.skips, "plan skip set disagrees with recipe partition")
    totals_mismatch = plan.totals.actions != counts.actions or plan.totals.skips != counts.skips
    if not allow_public_mismatch:
        _require(not totals_mismatch, "plan totals disagree with recipe partition")
    action_ids = [action.action_id for action in plan.actions]
    action_paths = [action.path for action in plan.actions]
    _require(len(set(action_ids)) == len(action_ids), "plan contains duplicate action IDs")
    _require(len(set(action_paths)) == len(action_paths), "plan contains duplicate action paths")
    _require(
        len({action.docmend_id for action in plan.actions}) == len(plan.actions),
        "plan contains duplicate document IDs",
    )
    skip_paths = [skip.path for skip in plan.skips]
    _require(len(set(skip_paths)) == len(skip_paths), "plan contains duplicate skip paths")
    _require(not set(action_paths) & set(skip_paths), "plan action and skip paths overlap")
    by_path = {action.path: action for action in plan.actions}
    skips = {skip.path: skip for skip in plan.skips}
    inventory_by_path = {record.path: record for record in inventory.files}
    for recipe in iter_recipes(count):
        expected_output = expected_boundary_output(recipe)
        if recipe.recipe_class is ScaleRecipeClass.CLEAN_MARKDOWN:
            _require(
                recipe.path not in by_path and recipe.path not in skips,
                f"plan no-op partition disagrees for {recipe.path}",
            )
            continue
        if recipe.recipe_class is ScaleRecipeClass.BELOW_FLOOR_SKIP:
            decision = skips.get(recipe.path)
            _require(
                decision is not None and decision.reason == "below-non-ascii-floor",
                f"plan skip partition disagrees for {recipe.path}",
            )
            continue
        action = by_path.get(recipe.path)
        _require(action is not None, f"plan action partition disagrees for {recipe.path}")
        assert action is not None
        source = render_recipe(recipe)
        expected_target = expected_output.path if expected_output.path != recipe.path else None
        _require(
            action.action_id.startswith(f"{plan.run_id}/a"),
            f"plan action ID provenance disagrees for {recipe.path}",
        )
        _require(
            action.source_size_bytes == len(source) and action.source_sha256 == _sha256(source),
            f"plan source binding disagrees for {recipe.path}",
        )
        _require(
            tuple(action.operations) == _EXPECTED_OPERATIONS[recipe.recipe_class],
            f"plan operations disagree for {recipe.path}",
        )
        _require(
            action.target_path == expected_target,
            f"plan target disagrees for {recipe.path}",
        )
        _require(
            action.provenance.newline_style == recipe.newline
            and action.provenance.detected_encoding
            == inventory_by_path[recipe.path].encoding.detected,
            f"plan provenance disagrees for {recipe.path}",
        )
    return by_path, "conservation-mismatch" if totals_mismatch else None


def _report_contract(
    report: Report,
    *,
    plan: Plan,
    plan_sha256: str,
    plan_actions: Mapping[str, PlanAction],
    paths: PipelinePaths,
    count: int,
    allow_public_mismatch: bool = False,
) -> PublicPipelineFailure | None:
    _require(
        report.generated_by == f"docmend {__version__}",
        "report producer version disagrees with the candidate",
    )
    action_ids = {action.action_id for action in plan.actions}
    outcome_ids = [outcome.action_id for outcome in report.outcomes]
    _require(len(set(outcome_ids)) == len(outcome_ids), "report contains duplicate outcomes")
    _require(set(outcome_ids) == action_ids, "report outcome set disagrees with plan actions")
    totals_mismatch = not (
        report.totals.applied == len(action_ids)
        and report.totals.would_apply == 0
        and report.totals.skipped == 0
        and report.totals.failed == 0
        and report.totals.not_attempted == 0
    )
    if not allow_public_mismatch:
        _require(not totals_mismatch, "report totals disagree with complete apply outcomes")
    _require(not report.dry_run, "report records a dry run instead of binding apply")
    _require(
        report.plan_ref.path == str(paths.plan)
        and report.plan_ref.run_id == plan.run_id
        and report.plan_ref.sha256 == plan_sha256,
        "report plan binding disagrees with the validated snapshot",
    )
    _require(report.prior_attempt is None, "report unexpectedly names a prior attempt")
    _require(report.manifest_sha256 is not None, "report omits its manifest hash")
    outcomes_by_id = {outcome.action_id: outcome for outcome in report.outcomes}
    for recipe in iter_recipes(count):
        if recipe.recipe_class in {
            ScaleRecipeClass.CLEAN_MARKDOWN,
            ScaleRecipeClass.BELOW_FLOOR_SKIP,
        }:
            continue
        action = plan_actions.get(recipe.path)
        _require(action is not None, f"report action binding disagrees for {recipe.path}")
        assert action is not None
        outcome = outcomes_by_id.get(action.action_id)
        _require(outcome is not None, f"report outcome is missing for {recipe.path}")
        assert outcome is not None
        expected = expected_boundary_output(recipe)
        _require(
            outcome.path == action.path
            and outcome.status == "applied"
            and outcome.before_sha256 == action.source_sha256
            and outcome.after_sha256 == expected.sha256
            and outcome.skip_reason is None
            and outcome.error is None,
            f"report outcome disagrees for {action.path}",
        )
    return "conservation-mismatch" if totals_mismatch else None


def _manifest_contract(
    chain: ManifestChain,
    snapshot: _FileSnapshot,
    *,
    report: Report,
    plan: Plan,
    plan_sha256: str,
    paths: PipelinePaths,
) -> None:
    expected_lines = 1 + 2 * len(plan.actions)
    _require(snapshot.data.endswith(b"\n"), "manifest lacks its terminal newline")
    lines = snapshot.data.splitlines()
    _require(
        len(lines) == expected_lines and all(lines),
        "manifest record count must be exactly 1 + 2 * plan actions",
    )
    _require(len(chain.sets) == 1, "manifest chain must contain one apply set")
    manifest_set = chain.sets[0]
    header = manifest_set.header
    _require(
        header.kind == "apply"
        and header.run_id == report.run_id
        and header.source_root == str(paths.corpus)
        and header.backup_root is None
        and header.plan_sha256 == plan_sha256
        and header.prior_manifest_sha256 is None
        and header.prior_attempt is None,
        "manifest header binding disagrees with plan/report/corpus",
    )
    _require(
        header.effective_excludes == tuple(DocmendConfig().paths.exclude),
        "manifest header binding disagrees with exact default excludes",
    )
    _require(
        manifest_set.sha256 == snapshot.sha256 and report.manifest_sha256 == snapshot.sha256,
        "report manifest binding disagrees with validated bytes",
    )
    records = manifest_set.records
    _require(len(records) == 2 * len(plan.actions), "manifest lifecycle record count disagrees")
    results = Counter((record.action_id, record.result) for record in records)
    expected = Counter(
        (action.action_id, result) for action in plan.actions for result in ("intent", "applied")
    )
    _require(results == expected, "manifest intent-to-applied lifecycle disagrees with plan")
    _require(
        [record.seq for record in records] == list(range(1, len(records) + 1)),
        "manifest sequence is not contiguous",
    )
    try:
        lifecycle = reduce_lifecycle(chain)
    except ArtifactError as exc:
        raise QualificationFailure("manifest lifecycle could not be reduced") from exc
    _require(
        set(lifecycle) == {action.action_id for action in plan.actions}
        and all(value.state == "applied" for value in lifecycle.values()),
        "manifest lifecycle is not fully applied",
    )
    actions = {action.action_id: action for action in plan.actions}
    outcomes = {outcome.action_id: outcome for outcome in report.outcomes}
    operation_by_action = {
        action.action_id: (
            "rename"
            if tuple(action.operations) == ("rename",)
            else "rename_and_rewrite"
            if action.target_path is not None
            else "rewrite"
        )
        for action in plan.actions
    }
    for record in records:
        action = actions[record.action_id]
        outcome = outcomes.get(record.action_id)
        _require(
            outcome is not None,
            f"manifest record lacks a report outcome for {record.action_id}",
        )
        assert outcome is not None
        target_relative = action.target_path if action.target_path is not None else action.path
        expected_original = str(paths.corpus / action.path)
        expected_target = str(paths.corpus / target_relative)
        _require(
            record.run_id == report.run_id
            and record.docmend_id == action.docmend_id
            and record.operation == operation_by_action[action.action_id]
            and record.original_path == expected_original
            and record.target_path == expected_target
            and record.before_sha256 == action.source_sha256
            and record.after_sha256 == outcome.after_sha256,
            f"manifest record binding disagrees for {action.action_id}",
        )
        _require(
            record.backup_path is None
            and record.error is None
            and record.overwritten_sha256 is None
            and record.overwritten_backup_path is None
            and record.undoes_action_id is None
            and record.undoes_run_id is None
            and record.target_identity is None,
            f"manifest record carries unexpected backup/error/undo state for {action.action_id}",
        )
        _require(
            record.source_identity is not None and record.expected_published_identity is not None,
            f"manifest record omits required object identity for {action.action_id}",
        )
        assert record.source_identity is not None
        assert record.expected_published_identity is not None
        if record.result == "applied":
            try:
                published_metadata = (paths.corpus / target_relative).lstat()
            except OSError as exc:
                raise QualificationFailure(
                    f"manifest published object is unavailable for {action.action_id}"
                ) from exc
            _require_identity(
                stat.S_ISREG(published_metadata.st_mode)
                and (
                    record.expected_published_identity.dev,
                    record.expected_published_identity.ino,
                )
                == (published_metadata.st_dev, published_metadata.st_ino),
                f"manifest published object identity disagrees for {action.action_id}",
            )
        if record.operation == "rename":
            _require(
                record.source_identity == record.expected_published_identity,
                f"manifest pure-rename identity disagrees for {action.action_id}",
            )
        else:
            _require(
                record.source_identity != record.expected_published_identity,
                f"manifest rewrite identity did not change for {action.action_id}",
            )


def verification_finding_keys(report: VerifyReport) -> tuple[FindingKey, ...]:
    """Return the sorted duplicate-preserving verification finding multiset."""

    return tuple(
        sorted(cast("FindingKey", (finding.path, finding.check)) for finding in report.findings)
    )


def _boundary_contract(paths: PipelinePaths, *, count: int) -> None:
    for recipe in boundary_samples(count):
        expected = expected_boundary_output(recipe)
        target = paths.corpus / expected.path
        try:
            data = _snapshot(target, kind="boundary output").data
        except QualificationIncomplete as exc:
            raise QualificationFailure(f"boundary output is missing for {recipe.path}") from exc
        _require(data == expected.data, f"boundary bytes disagree for {recipe.path}")
        _require(_sha256(data) == expected.sha256, f"boundary hash disagrees for {recipe.path}")
        if expected.encoding == "utf-8":
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise QualificationFailure(
                    f"boundary encoding disagrees for {recipe.path}"
                ) from exc
        else:
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    data.decode("cp1252")
                except UnicodeDecodeError as exc:
                    raise QualificationFailure(
                        f"boundary encoding disagrees for {recipe.path}"
                    ) from exc
            else:
                raise QualificationFailure(f"boundary encoding disagrees for {recipe.path}")
        if expected.path != recipe.path:
            original = paths.corpus / recipe.path
            try:
                original.lstat()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise QualificationFailure(
                    f"boundary original path is unreadable for {recipe.path}"
                ) from exc
            else:
                raise QualificationFailure(
                    f"boundary rename left the original path for {recipe.path}"
                )


def _freeze_counts(values: Counter[FindingKey]) -> Mapping[FindingKey, int]:
    return MappingProxyType(dict(values))


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON object key")
        document[key] = value
    return document


def _finite_json_float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


def _reject_json_constant(_raw: str) -> object:
    raise ValueError("non-finite JSON constant")


def _require_unicode_scalars(document: object) -> None:
    pending = [document]
    while pending:
        value = pending.pop()
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("JSON string contains a non-scalar value") from exc
        elif type(value) is list:
            pending.extend(cast("list[object]", value))
        elif type(value) is dict:
            for key, item in cast("dict[str, object]", value).items():
                pending.extend((key, item))


def _parse_structured_log_record(raw: str, *, stage: str, run_id: str) -> None:
    kind = f"{stage} structured log"
    try:
        document = cast(
            "object",
            json.loads(
                raw,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
                parse_float=_finite_json_float,
            ),
        )
        _require_unicode_scalars(document)
    except (RecursionError, ValueError) as exc:
        raise QualificationIncomplete(f"{kind} contains invalid strict JSON") from exc
    _require_identity(type(document) is dict, f"{kind} record must be a JSON object")
    record = cast("dict[str, object]", document)
    _require_identity(
        record.get("run_id") == run_id and record.get("command") == stage,
        f"{kind} correlation disagrees with its artifact",
    )
    _require_identity(
        type(record.get("event")) is str and record["event"] != "",
        f"{kind} event is invalid",
    )
    _require_identity(
        type(record.get("level")) is str and record["level"] in _STRUCTURED_LOG_LEVELS,
        f"{kind} level is invalid",
    )
    timestamp = record.get("ts")
    _require_identity(type(timestamp) is str, f"{kind} timestamp is invalid")
    assert isinstance(timestamp, str)
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise QualificationIncomplete(f"{kind} timestamp is invalid") from exc
    _require_identity(
        parsed_timestamp.tzinfo is not None and parsed_timestamp.utcoffset() is not None,
        f"{kind} timestamp is not timezone-aware",
    )


def _stage_log_snapshot(
    paths: PipelinePaths,
    *,
    stage: str,
    run_id: str,
) -> _FileSnapshot:
    snapshot = _snapshot(
        paths.pipeline / ".docmend" / f"docmend-{run_id}.jsonl",
        kind=f"{stage} structured log",
    )
    kind = f"{stage} structured log"
    _require_identity(snapshot.size > 0, f"{kind} is empty")
    _require_identity(snapshot.data.endswith(b"\n"), f"{kind} lacks its terminal newline")
    try:
        text = snapshot.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise QualificationIncomplete(f"{kind} is not strict UTF-8") from exc
    records = text.removesuffix("\n").split("\n")
    _require_identity(bool(records) and all(records), f"{kind} contains an empty record")
    for record in records:
        _parse_structured_log_record(record, stage=stage, run_id=run_id)
    _require_unchanged(snapshot, kind=f"{stage} structured log")
    return snapshot


def validate_pipeline_prefix(
    paths: PipelinePaths,
    *,
    count: int,
    through: str,
) -> PipelinePrefixReconciliation:
    """Enforce every available cross-artifact boundary before the next stage."""

    if through not in {"scan", "plan", "apply", "verify"}:
        raise ValueError("pipeline prefix must end at scan, plan, apply, or verify")
    try:
        recipe_counts(count)
    except ValueError as exc:
        raise QualificationIncomplete("pipeline count is outside the scale contract") from exc
    paths = _absolute_paths(paths)
    if through == "verify":
        reconciliation = reconcile_pipeline(paths, count=count, _allow_public_mismatch=True)
        return PipelinePrefixReconciliation(
            stage="verify",
            run_id=reconciliation.stage_run_ids["verify"],
            artifact_bytes=MappingProxyType(
                {
                    "verify-report": reconciliation.artifact_bytes["verify-report"],
                    "structured-log": reconciliation.structured_log_bytes["verify"],
                }
            ),
            verified_actions=reconciliation.verified_actions,
            observed_findings=sum(reconciliation.observed_findings.values()),
            public_failure=reconciliation.public_failure,
        )
    inventory_snapshot = _snapshot(paths.inventory, kind="inventory")
    inventory = _direct_read(inventory_snapshot, read_inventory, kind="inventory")
    _require_unchanged(inventory_snapshot, kind="inventory")
    scan_log = _stage_log_snapshot(paths, stage="scan", run_id=inventory.run_id)
    _inventory_identity_contract(inventory, paths=paths)
    if through == "scan":
        try:
            public_failure = _inventory_contract(
                inventory,
                count=count,
                paths=paths,
                allow_public_mismatch=True,
            )
        except QualificationFailure:
            public_failure = "conservation-mismatch"
        _require_unchanged(inventory_snapshot, kind="inventory")
        _require_unchanged(scan_log, kind="scan structured log")
        return PipelinePrefixReconciliation(
            stage="scan",
            run_id=inventory.run_id,
            artifact_bytes=MappingProxyType(
                {
                    "inventory": inventory_snapshot.size,
                    "structured-log": scan_log.size,
                }
            ),
            scanned_files=inventory.totals.files,
            public_failure=public_failure,
        )

    plan_snapshot = _snapshot(paths.plan, kind="plan")
    plan, plan_sha256 = _direct_read(
        plan_snapshot,
        read_plan_snapshot,
        kind="plan",
    )
    _require_unchanged(plan_snapshot, kind="plan")
    _require_identity(
        plan_sha256 == plan_snapshot.sha256,
        "plan reader digest disagrees with snapshot",
    )
    plan_log = _stage_log_snapshot(paths, stage="plan", run_id=plan.run_id)
    _plan_identity_contract(
        plan,
        inventory=inventory,
        inventory_sha256=inventory_snapshot.sha256,
        paths=paths,
    )
    if through == "plan":
        public_failure: PublicPipelineFailure | None = None
        try:
            inventory_failure = _inventory_contract(
                inventory,
                count=count,
                paths=paths,
                allow_public_mismatch=True,
            )
        except QualificationFailure:
            inventory_failure = "conservation-mismatch"
        public_failure = _select_public_failure(public_failure, inventory_failure)
        try:
            _, plan_failure = _plan_contract(
                plan,
                inventory=inventory,
                inventory_sha256=inventory_snapshot.sha256,
                paths=paths,
                count=count,
                allow_public_mismatch=True,
            )
        except QualificationFailure:
            plan_failure = "conservation-mismatch"
        public_failure = _select_public_failure(public_failure, plan_failure)
        for snapshot, kind in (
            (inventory_snapshot, "inventory"),
            (scan_log, "scan structured log"),
            (plan_snapshot, "plan"),
            (plan_log, "plan structured log"),
        ):
            _require_unchanged(snapshot, kind=kind)
        return PipelinePrefixReconciliation(
            stage="plan",
            run_id=plan.run_id,
            artifact_bytes=MappingProxyType(
                {
                    "plan": plan_snapshot.size,
                    "structured-log": plan_log.size,
                }
            ),
            planned_actions=plan.totals.actions,
            plan_skips=plan.totals.skips,
            plan_noops=_observed_plan_noops(plan, count=count),
            public_failure=public_failure,
        )

    report_snapshot = _snapshot(paths.report, kind="report")
    report, report_sha256 = _direct_read(
        report_snapshot,
        read_report_snapshot,
        kind="report",
    )
    _require_unchanged(report_snapshot, kind="report")
    _require_identity(
        report_sha256 == report_snapshot.sha256,
        "report reader digest disagrees with snapshot",
    )
    _report_identity_contract(
        report,
        plan=plan,
        plan_sha256=plan_sha256,
        paths=paths,
    )
    manifest_path = paths.pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    manifest_snapshot = _snapshot(manifest_path, kind="manifest")
    chain = _direct_read(
        manifest_snapshot,
        lambda captured: read_manifest_chain((captured,), check_backup_objects=False),
        kind="manifest",
    )
    _require_unchanged(manifest_snapshot, kind="manifest")
    _manifest_identity_contract(
        chain,
        manifest_snapshot,
        report=report,
        plan=plan,
        plan_sha256=plan_sha256,
        paths=paths,
    )
    apply_log = _stage_log_snapshot(paths, stage="apply", run_id=report.run_id)
    if through == "apply":
        public_failure = None
        try:
            inventory_failure = _inventory_contract(
                inventory,
                count=count,
                paths=paths,
                allow_public_mismatch=True,
            )
        except QualificationFailure:
            inventory_failure = "conservation-mismatch"
        public_failure = _select_public_failure(public_failure, inventory_failure)
        try:
            plan_actions, plan_failure = _plan_contract(
                plan,
                inventory=inventory,
                inventory_sha256=inventory_snapshot.sha256,
                paths=paths,
                count=count,
                allow_public_mismatch=True,
            )
        except QualificationFailure:
            plan_actions = {action.path: action for action in plan.actions}
            plan_failure = "conservation-mismatch"
        public_failure = _select_public_failure(public_failure, plan_failure)
        try:
            report_failure = _report_contract(
                report,
                plan=plan,
                plan_sha256=plan_sha256,
                plan_actions=plan_actions,
                paths=paths,
                count=count,
                allow_public_mismatch=True,
            )
        except QualificationFailure:
            report_failure = "conservation-mismatch"
        public_failure = _select_public_failure(public_failure, report_failure)
        try:
            _manifest_contract(
                chain,
                manifest_snapshot,
                report=report,
                plan=plan,
                plan_sha256=plan_sha256,
                paths=paths,
            )
        except QualificationFailure:
            public_failure = _select_public_failure(public_failure, "conservation-mismatch")
        for snapshot, kind in (
            (inventory_snapshot, "inventory"),
            (scan_log, "scan structured log"),
            (plan_snapshot, "plan"),
            (plan_log, "plan structured log"),
            (report_snapshot, "report"),
            (manifest_snapshot, "manifest"),
            (apply_log, "apply structured log"),
        ):
            _require_unchanged(snapshot, kind=kind)
        return PipelinePrefixReconciliation(
            stage="apply",
            run_id=report.run_id,
            artifact_bytes=MappingProxyType(
                {
                    "report": report_snapshot.size,
                    "manifest": manifest_snapshot.size,
                    "structured-log": apply_log.size,
                }
            ),
            applied_actions=report.totals.applied,
            apply_skips=report.totals.skipped,
            failures=report.totals.failed,
            not_attempted=report.totals.not_attempted,
            public_failure=public_failure,
        )
    raise AssertionError("unreachable pipeline prefix")


def reconcile_pipeline(
    paths: PipelinePaths,
    *,
    count: int,
    _allow_public_mismatch: bool = False,
) -> PipelineReconciliation:
    """Validate every artifact, lifecycle edge, finding, and boundary oracle."""

    try:
        recipe_counts(count)
    except ValueError as exc:
        raise QualificationIncomplete("pipeline count is outside the scale contract") from exc
    paths = _absolute_paths(paths)

    inventory_snapshot = _snapshot(paths.inventory, kind="inventory")
    inventory = _direct_read(inventory_snapshot, read_inventory, kind="inventory")
    _require_unchanged(inventory_snapshot, kind="inventory")

    plan_snapshot = _snapshot(paths.plan, kind="plan")
    plan, plan_sha256 = _direct_read(
        plan_snapshot,
        read_plan_snapshot,
        kind="plan",
    )
    _require_unchanged(plan_snapshot, kind="plan")
    _require_identity(
        plan_sha256 == plan_snapshot.sha256,
        "plan reader digest disagrees with snapshot",
    )

    report_snapshot = _snapshot(paths.report, kind="report")
    report, report_sha256 = _direct_read(
        report_snapshot,
        read_report_snapshot,
        kind="report",
    )
    _require_unchanged(report_snapshot, kind="report")
    _require_identity(
        report_sha256 == report_snapshot.sha256,
        "report reader digest disagrees with snapshot",
    )

    manifest_path = paths.pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    manifest_snapshot = _snapshot(manifest_path, kind="manifest")
    chain = _direct_read(
        manifest_snapshot,
        lambda captured: read_manifest_chain((captured,), check_backup_objects=False),
        kind="manifest",
    )
    _require_unchanged(manifest_snapshot, kind="manifest")

    verify_snapshot = _snapshot(paths.verify_report, kind="verify-report")
    verify_report = _direct_read(
        verify_snapshot,
        read_verify_report,
        kind="verify-report",
    )
    _require_unchanged(verify_snapshot, kind="verify-report")
    _require_identity(
        verify_report.generated_by == f"docmend {__version__}",
        "verify-report producer version disagrees with the candidate",
    )
    _require_identity(
        verify_report.verified_path == str(paths.corpus)
        and verify_report.source_root == str(paths.corpus),
        "verify corpus binding disagrees",
    )

    _inventory_identity_contract(inventory, paths=paths)
    _plan_identity_contract(
        plan,
        inventory=inventory,
        inventory_sha256=inventory_snapshot.sha256,
        paths=paths,
    )
    _report_identity_contract(
        report,
        plan=plan,
        plan_sha256=plan_sha256,
        paths=paths,
    )
    _manifest_identity_contract(
        chain,
        manifest_snapshot,
        report=report,
        plan=plan,
        plan_sha256=plan_sha256,
        paths=paths,
    )

    try:
        with ExitStack() as captured:
            captured_manifest = captured.enter_context(_captured_path(manifest_snapshot))
            captured_report = captured.enter_context(_captured_path(report_snapshot))
            evidence = load_verification_evidence(
                paths.plan,
                (captured_manifest,),
                (captured_report,),
                plan_snapshot=(plan, plan_sha256),
            )
        coverage = check_plan_coverage(evidence)
    except (ArtifactError, OSError, ValueError) as exc:
        raise QualificationIncomplete(
            "validated plan/report/manifest snapshots disagreed during coverage loading"
        ) from exc
    _require_identity(
        not any(finding.check == "coverage-binding" for finding in evidence.findings),
        "verification evidence contains binding findings",
    )
    input_paths = {
        "plan": paths.plan,
        "manifest": manifest_path,
        "report": paths.report,
    }
    normalized_inputs = tuple(
        item.model_copy(update={"path": str(input_paths[item.kind])}) for item in evidence.inputs
    )
    _require_identity(
        tuple(verify_report.inputs) == normalized_inputs,
        "verify input bindings disagree with validated artifact snapshots",
    )

    stage_run_ids = {
        "scan": inventory.run_id,
        "plan": plan.run_id,
        "apply": report.run_id,
        "verify": verify_report.run_id,
    }
    structured_log_bytes: dict[str, int] = {}
    log_snapshots: list[_FileSnapshot] = []
    for stage, run_id in stage_run_ids.items():
        snapshot = _stage_log_snapshot(paths, stage=stage, run_id=run_id)
        structured_log_bytes[stage] = snapshot.size
        log_snapshots.append(snapshot)

    public_failure: PublicPipelineFailure | None = None
    try:
        inventory_failure = _inventory_contract(
            inventory,
            count=count,
            paths=paths,
            allow_public_mismatch=True,
        )
    except QualificationFailure:
        inventory_failure = "conservation-mismatch"
    public_failure = _select_public_failure(public_failure, inventory_failure)
    try:
        plan_actions, plan_failure = _plan_contract(
            plan,
            inventory=inventory,
            inventory_sha256=inventory_snapshot.sha256,
            paths=paths,
            count=count,
            allow_public_mismatch=True,
        )
    except QualificationFailure:
        plan_actions = {action.path: action for action in plan.actions}
        plan_failure = "conservation-mismatch"
    public_failure = _select_public_failure(public_failure, plan_failure)
    try:
        report_failure = _report_contract(
            report,
            plan=plan,
            plan_sha256=plan_sha256,
            plan_actions=plan_actions,
            paths=paths,
            count=count,
            allow_public_mismatch=True,
        )
    except QualificationFailure:
        report_failure = "conservation-mismatch"
    public_failure = _select_public_failure(public_failure, report_failure)
    try:
        _manifest_contract(
            chain,
            manifest_snapshot,
            report=report,
            plan=plan,
            plan_sha256=plan_sha256,
            paths=paths,
        )
    except QualificationFailure:
        public_failure = _select_public_failure(public_failure, "conservation-mismatch")

    expected_findings = Counter(expected_finding_keys(count))
    observed_findings = Counter(verification_finding_keys(verify_report))
    finding_mismatch = observed_findings != expected_findings
    public_failure = _select_public_failure(
        public_failure,
        "finding-mismatch" if finding_mismatch else None,
    )
    coverage_mismatch = (
        verify_report.checked_files != count
        or bool(evidence.findings)
        or bool(coverage.findings)
        or coverage.outcomes != {action.action_id: "applied" for action in plan.actions}
    )
    public_failure = _select_public_failure(
        public_failure,
        "conservation-mismatch" if coverage_mismatch else None,
    )
    try:
        _boundary_contract(paths, count=count)
    except QualificationFailure:
        public_failure = _select_public_failure(public_failure, "conservation-mismatch")

    for snapshot in (
        inventory_snapshot,
        plan_snapshot,
        report_snapshot,
        manifest_snapshot,
        verify_snapshot,
        *log_snapshots,
    ):
        _require_unchanged(snapshot, kind=snapshot.path.name)

    if public_failure is not None and not _allow_public_mismatch:
        raise QualificationFailure(public_failure)

    return PipelineReconciliation(
        count=count,
        scanned_files=inventory.totals.files,
        planned_actions=plan.totals.actions,
        plan_skips=plan.totals.skips,
        plan_noops=_observed_plan_noops(plan, count=count),
        applied_actions=report.totals.applied,
        verified_actions=len(coverage.outcomes),
        stage_run_ids=MappingProxyType(stage_run_ids),
        artifact_bytes=MappingProxyType(
            {
                "inventory": inventory_snapshot.size,
                "plan": plan_snapshot.size,
                "report": report_snapshot.size,
                "manifest": manifest_snapshot.size,
                "verify-report": verify_snapshot.size,
            }
        ),
        structured_log_bytes=MappingProxyType(structured_log_bytes),
        expected_findings=_freeze_counts(expected_findings),
        observed_findings=_freeze_counts(observed_findings),
        manifest_path=manifest_path,
        public_failure=public_failure,
    )
