"""Whole-pipeline reconciliation contracts for NFR-001 qualification."""

import gc
import hashlib
import json
import os
from collections import Counter
from collections.abc import Collection, Iterator
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from docmend.artifacts import read_report_snapshot, read_verify_report
from docmend.cli import app
from docmend.scale_corpus import (
    ExpectedBoundaryOutput,
    ScaleRecipe,
    boundary_samples,
    expected_boundary_output,
    expected_finding_keys,
    materialize_scale_corpus,
    recipe_counts,
)
from docmend.scale_reconcile import (
    PipelinePaths,
    QualificationFailure,
    QualificationIncomplete,
    reconcile_pipeline,
    validate_pipeline_prefix,
    verification_finding_keys,
)

COUNT = 40


def _run_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    count: int,
) -> PipelinePaths:
    pipeline = tmp_path / f"pipeline-{count}"
    pipeline.mkdir()
    corpus = pipeline / "corpus"
    materialize_scale_corpus(corpus, count)
    inventory = pipeline / "inventory.json"
    plan = pipeline / "plan.json"
    report = pipeline / "report.json"
    verify_report = pipeline / "verify.json"
    monkeypatch.chdir(pipeline)
    runner = CliRunner()
    commands = (
        ["scan", str(corpus), "--report", str(inventory)],
        ["plan", "--inventory", str(inventory), "--out", str(plan)],
        [
            "apply",
            str(plan),
            "--write",
            "--preserved-by",
            "external",
            "--report",
            str(report),
        ],
    )
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0, result.output
    report_model, _report_sha256 = read_report_snapshot(report)
    manifest = pipeline / ".docmend" / f"docmend-{report_model.run_id}-manifest.jsonl"
    verify = runner.invoke(
        app,
        [
            "verify",
            str(corpus),
            "--plan",
            str(plan),
            "--manifest",
            str(manifest),
            "--report",
            str(report),
            "--out",
            str(verify_report),
        ],
    )
    assert verify.exit_code == 1, verify.output
    return PipelinePaths(
        pipeline=pipeline,
        corpus=corpus,
        inventory=inventory,
        plan=plan,
        report=report,
        verify_report=verify_report,
    )


@pytest.fixture
def valid_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PipelinePaths:
    return _run_pipeline(tmp_path, monkeypatch, count=COUNT)


type JsonObject = dict[str, object]


def _mapping(value: object) -> JsonObject:
    assert isinstance(value, dict)
    return cast("JsonObject", value)


def _mappings(value: object) -> list[JsonObject]:
    assert isinstance(value, list)
    items = cast("list[object]", value)
    assert all(isinstance(item, dict) for item in items)
    return cast("list[JsonObject]", items)


def _integer(mapping: JsonObject, key: str) -> int:
    value = mapping[key]
    assert type(value) is int
    return value


def _document(path: Path) -> JsonObject:
    return _mapping(json.loads(path.read_text(encoding="utf-8")))


def _write_document(path: Path, document: JsonObject) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _set_attribute(value: object, name: str, replacement: object) -> None:
    setattr(value, name, replacement)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rebind_verify_inputs(paths: PipelinePaths, manifest: Path) -> None:
    document = _document(paths.verify_report)
    inputs = _mappings(document["inputs"])
    digests = {
        "plan": _sha256(paths.plan),
        "manifest": _sha256(manifest),
        "report": _sha256(paths.report),
    }
    for item in inputs:
        item["sha256"] = digests[cast("str", item["kind"])]
    _write_document(paths.verify_report, document)


def test_reconcile_pipeline__returns_frozen_complete_contract(
    valid_pipeline: PipelinePaths,
) -> None:
    result = reconcile_pipeline(valid_pipeline, count=COUNT)
    counts = recipe_counts(COUNT)

    assert result.count == COUNT
    assert result.scanned_files == COUNT
    assert result.planned_actions == counts.actions
    assert result.plan_skips == counts.skips
    assert result.plan_noops == counts.noops
    assert result.applied_actions == counts.actions
    assert result.verified_actions == counts.actions
    assert result.expected_findings == Counter(expected_finding_keys(COUNT))
    assert result.observed_findings == result.expected_findings
    assert set(result.stage_run_ids) == {"scan", "plan", "apply", "verify"}
    assert set(result.artifact_bytes) == {
        "inventory",
        "plan",
        "report",
        "manifest",
        "verify-report",
    }
    assert all(size > 0 for size in result.artifact_bytes.values())
    assert set(result.structured_log_bytes) == {"scan", "plan", "apply", "verify"}
    assert all(size > 0 for size in result.structured_log_bytes.values())
    assert result.manifest_path == (
        valid_pipeline.pipeline
        / ".docmend"
        / f"docmend-{result.stage_run_ids['apply']}-manifest.jsonl"
    )
    with pytest.raises(FrozenInstanceError):
        _set_attribute(result, "count", 39)


def test_reconcile_pipeline__derives_non_bucket_count_without_fixed_offsets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    count = 41
    pipeline = _run_pipeline(tmp_path, monkeypatch, count=count)

    result = reconcile_pipeline(pipeline, count=count)

    assert result.planned_actions == recipe_counts(count).actions
    assert result.plan_noops == recipe_counts(count).noops
    assert result.plan_skips == recipe_counts(count).skips


def test_reconciliation__recipe_oracle_remains_unsized_and_unretained(
    valid_pipeline: PipelinePaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docmend import scale_reconcile

    original_iter = scale_reconcile.iter_recipes
    original_boundary = scale_reconcile.expected_boundary_output
    original_render = scale_reconcile.render_recipe

    class UnsizedRecipes:
        def __init__(self, values: Iterator[ScaleRecipe]) -> None:
            self._values = values

        def __iter__(self) -> Iterator[ScaleRecipe]:
            return self

        def __next__(self) -> ScaleRecipe:
            return next(self._values)

        def __length_hint__(self) -> int:
            raise AssertionError("recipe stream requested a sized materialization")

    def guarded_iter(count: int) -> Iterator[ScaleRecipe]:
        return UnsizedRecipes(iter(original_iter(count)))

    def require_unretained(recipe: ScaleRecipe) -> None:
        for referrer in gc.get_referrers(recipe):
            if isinstance(referrer, dict):
                mapping = cast("dict[object, object]", referrer)
                if mapping.get(recipe.path) is recipe:
                    raise AssertionError("recipe stream retained a path-to-recipe map")
            elif isinstance(referrer, (list, set, tuple)):
                collection = cast("Collection[object]", referrer)
                if any(item is recipe for item in collection):
                    raise AssertionError("recipe stream retained a sized recipe collection")

    def guarded_boundary(recipe: ScaleRecipe) -> ExpectedBoundaryOutput:
        require_unretained(recipe)
        return original_boundary(recipe)

    def guarded_render(recipe: ScaleRecipe) -> bytes:
        require_unretained(recipe)
        return original_render(recipe)

    monkeypatch.setattr(scale_reconcile, "iter_recipes", guarded_iter)
    monkeypatch.setattr(scale_reconcile, "expected_boundary_output", guarded_boundary)
    monkeypatch.setattr(scale_reconcile, "render_recipe", guarded_render)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")

    assert prefix.public_failure is None


def test_reconcile_pipeline__missing_direct_artifact_is_incomplete(
    valid_pipeline: PipelinePaths,
) -> None:
    valid_pipeline.inventory.unlink()

    with pytest.raises(QualificationIncomplete, match="inventory"):
        reconcile_pipeline(valid_pipeline, count=COUNT)


def test_reconcile_pipeline__owner_readers_consume_captured_bytes_during_aba_swap(
    valid_pipeline: PipelinePaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docmend import scale_reconcile

    original_reader = scale_reconcile.read_inventory
    original = valid_pipeline.inventory
    held = original.with_name("held-inventory.json")
    malicious = original.with_name("malicious-inventory.json")
    malicious_document = _document(original)
    malicious_document["generated_by"] = "wrong producer"
    _write_document(malicious, malicious_document)

    def read_during_swap(path: Path):  # type: ignore[no-untyped-def]
        original.replace(held)
        malicious.replace(original)
        try:
            return original_reader(path)
        finally:
            original.unlink()
            held.replace(original)

    monkeypatch.setattr(scale_reconcile, "read_inventory", read_during_swap)

    assert reconcile_pipeline(valid_pipeline, count=COUNT).count == COUNT


@pytest.mark.parametrize("artifact", ["inventory", "plan", "report", "verify_report"])
def test_artifacts__must_bind_exact_candidate_producer(
    valid_pipeline: PipelinePaths,
    artifact: str,
) -> None:
    path = getattr(valid_pipeline, artifact)
    document = _document(path)
    document["generated_by"] = "docmend 9.9.9"
    _write_document(path, document)

    with pytest.raises(QualificationIncomplete, match="producer"):
        reconcile_pipeline(valid_pipeline, count=COUNT)


@pytest.mark.parametrize("mutation", ["count", "path", "size", "hash", "encoding", "newline"])
def test_inventory__exact_recipe_facts_are_required(
    valid_pipeline: PipelinePaths, mutation: str
) -> None:
    document = _document(valid_pipeline.inventory)
    files = _mappings(document["files"])
    first = files[0]
    if mutation == "count":
        totals = _mapping(document["totals"])
        totals["files"] = COUNT - 1
    elif mutation == "path":
        first["path"] = "lib/00/00/wrong.txt"
    elif mutation == "size":
        first["size_bytes"] = _integer(first, "size_bytes") + 1
    elif mutation == "hash":
        first["sha256"] = "sha256:" + "0" * 64
    elif mutation == "encoding":
        encoding = _mapping(first["encoding"])
        encoding["ascii_only"] = False
    else:
        first["newline_style"] = "crlf"
    _write_document(valid_pipeline.inventory, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="scan")

    assert prefix.public_failure == "conservation-mismatch"
    if mutation == "count":
        assert prefix.scanned_files == COUNT - 1


def test_inventory__coherently_rehashed_wrong_root_is_rejected(
    valid_pipeline: PipelinePaths,
) -> None:
    inventory = _document(valid_pipeline.inventory)
    inventory["requested_path"] = "/synthetic/wrong-root"
    inventory["source_root"] = "/synthetic/wrong-root"
    _write_document(valid_pipeline.inventory, inventory)

    plan = _document(valid_pipeline.plan)
    inventory_ref = _mapping(plan["inventory_ref"])
    inventory_ref["sha256"] = _sha256(valid_pipeline.inventory)
    _write_document(valid_pipeline.plan, plan)

    report = _document(valid_pipeline.report)
    plan_ref = _mapping(report["plan_ref"])
    plan_ref["sha256"] = _sha256(valid_pipeline.plan)
    _write_document(valid_pipeline.report, report)
    report_model, _digest = read_report_snapshot(valid_pipeline.report)
    manifest = (
        valid_pipeline.pipeline / ".docmend" / f"docmend-{report_model.run_id}-manifest.jsonl"
    )
    lines = manifest.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["plan_sha256"] = _sha256(valid_pipeline.plan)
    lines[0] = json.dumps(header, separators=(",", ":"), sort_keys=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["manifest_sha256"] = _sha256(manifest)
    _write_document(valid_pipeline.report, report)
    _rebind_verify_inputs(valid_pipeline, manifest)

    with pytest.raises(QualificationIncomplete, match="inventory root binding"):
        reconcile_pipeline(valid_pipeline, count=COUNT)


def test_plan__must_bind_inventory_snapshot(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.plan)
    inventory_ref = _mapping(document["inventory_ref"])
    inventory_ref["sha256"] = "sha256:" + "0" * 64
    _write_document(valid_pipeline.plan, document)

    with pytest.raises(QualificationIncomplete, match="inventory binding"):
        reconcile_pipeline(valid_pipeline, count=COUNT)


@pytest.mark.parametrize("mutation", ["partition", "duplicate-path", "duplicate-action"])
def test_plan__must_exactly_partition_recipe_dispositions(
    valid_pipeline: PipelinePaths, mutation: str
) -> None:
    document = _document(valid_pipeline.plan)
    actions = _mappings(document["actions"])
    totals = _mapping(document["totals"])
    if mutation == "partition":
        actions.pop()
        totals["actions"] = _integer(totals, "actions") - 1
    else:
        duplicate = dict(actions[0])
        if mutation == "duplicate-action":
            duplicate["path"] = actions[1]["path"]
        else:
            duplicate["action_id"] = actions[1]["action_id"]
        actions.append(duplicate)
        totals["actions"] = _integer(totals, "actions") + 1
    _write_document(valid_pipeline.plan, document)

    if mutation == "partition":
        prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="plan")
        assert prefix.public_failure == "conservation-mismatch"
        assert prefix.planned_actions == _integer(totals, "actions")
        assert prefix.plan_noops == recipe_counts(COUNT).noops
    else:
        with pytest.raises(QualificationIncomplete, match="duplicate"):
            validate_pipeline_prefix(valid_pipeline, count=COUNT, through="plan")


@pytest.mark.parametrize("mutation", ["binding", "outcome-set", "totals"])
def test_report__must_bind_plan_and_exact_outcome_set(
    valid_pipeline: PipelinePaths, mutation: str
) -> None:
    document = _document(valid_pipeline.report)
    totals = _mapping(document["totals"])
    outcomes = _mappings(document["outcomes"])
    if mutation == "binding":
        plan_ref = _mapping(document["plan_ref"])
        plan_ref["sha256"] = "sha256:" + "0" * 64
    elif mutation == "outcome-set":
        outcomes.pop()
        totals["applied"] = _integer(totals, "applied") - 1
    else:
        totals["applied"] = _integer(totals, "applied") - 1
        totals["failed"] = 1
    _write_document(valid_pipeline.report, document)

    if mutation == "binding":
        with pytest.raises(QualificationIncomplete, match="report plan binding"):
            validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")
    else:
        prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")
        assert prefix.public_failure == "conservation-mismatch"
        assert prefix.applied_actions == _integer(totals, "applied")


def test_manifest__requires_exact_header_and_intent_applied_lifecycle(
    valid_pipeline: PipelinePaths,
) -> None:
    report, _digest = read_report_snapshot(valid_pipeline.report)
    manifest = valid_pipeline.pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    manifest.write_text("\n".join(lines[:-2]) + "\n", encoding="utf-8")
    report_document = _document(valid_pipeline.report)
    report_document["manifest_sha256"] = _sha256(manifest)
    _write_document(valid_pipeline.report, report_document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")

    assert prefix.public_failure == "conservation-mismatch"


def test_manifest__coherently_rehashed_wrong_record_binding_is_rejected(
    valid_pipeline: PipelinePaths,
) -> None:
    report, _digest = read_report_snapshot(valid_pipeline.report)
    manifest = valid_pipeline.pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[1])
    action_id = first["action_id"]
    replacement = "00000000-0000-4000-8000-000000000001"
    for index in range(1, len(lines)):
        record = json.loads(lines[index])
        if record["action_id"] == action_id:
            record["docmend_id"] = replacement
            lines[index] = json.dumps(record, separators=(",", ":"), sort_keys=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_document = _document(valid_pipeline.report)
    report_document["manifest_sha256"] = _sha256(manifest)
    _write_document(valid_pipeline.report, report_document)
    _rebind_verify_inputs(valid_pipeline, manifest)

    with pytest.raises(QualificationIncomplete, match="manifest record binding"):
        reconcile_pipeline(valid_pipeline, count=COUNT)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("backup_root", "/synthetic/backup"),
        ("effective_excludes", ["**/.git/**"]),
    ],
)
def test_manifest__coherently_rehashed_wrong_header_policy_is_rejected(
    valid_pipeline: PipelinePaths,
    field: str,
    replacement: object,
) -> None:
    report, _digest = read_report_snapshot(valid_pipeline.report)
    manifest = valid_pipeline.pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header[field] = replacement
    lines[0] = json.dumps(header, separators=(",", ":"), sort_keys=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_document = _document(valid_pipeline.report)
    report_document["manifest_sha256"] = _sha256(manifest)
    _write_document(valid_pipeline.report, report_document)
    _rebind_verify_inputs(valid_pipeline, manifest)

    if field == "backup_root":
        prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")
        assert prefix.public_failure == "conservation-mismatch"
    else:
        with pytest.raises(QualificationIncomplete, match="manifest header binding"):
            reconcile_pipeline(valid_pipeline, count=COUNT)


def test_validate_pipeline_prefix__requires_current_stage_structured_log(
    valid_pipeline: PipelinePaths,
) -> None:
    inventory = _document(valid_pipeline.inventory)
    run_id = inventory["run_id"]
    assert isinstance(run_id, str)
    structured_log = valid_pipeline.pipeline / ".docmend" / f"docmend-{run_id}.jsonl"
    structured_log.unlink()

    with pytest.raises(QualificationIncomplete, match="scan structured log"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="scan")


@pytest.mark.parametrize(
    "payload_kind",
    ["malformed", "duplicate-key", "nonfinite", "not-object", "unterminated"],
)
def test_validate_pipeline_prefix__rejects_invalid_structured_log_jsonl(
    valid_pipeline: PipelinePaths,
    payload_kind: str,
) -> None:
    inventory = _document(valid_pipeline.inventory)
    run_id = inventory["run_id"]
    assert isinstance(run_id, str)
    structured_log = valid_pipeline.pipeline / ".docmend" / f"docmend-{run_id}.jsonl"
    valid = {
        "ts": "2026-07-13T13:41:00+00:00",
        "level": "INFO",
        "run_id": run_id,
        "command": "scan",
        "event": "scan.completed",
    }
    payload = {
        "malformed": b"not-json\n",
        "duplicate-key": (
            "{"
            '"ts":"2026-07-13T13:41:00+00:00",'
            '"level":"INFO",'
            f'"run_id":"{run_id}",'
            f'"run_id":"{run_id}",'
            '"command":"scan",'
            '"event":"scan.completed"'
            "}\n"
        ).encode(),
        "nonfinite": (json.dumps({**valid, "detail": 1})[:-1] + ',"value":NaN}\n').encode(),
        "not-object": b"[]\n",
        "unterminated": json.dumps(valid).encode(),
    }[payload_kind]
    structured_log.write_bytes(payload)

    with pytest.raises(QualificationIncomplete, match="scan structured log"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="scan")


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("run_id", "run_20260713T134100Z_ffffff"),
        ("command", "plan"),
        ("event", ""),
        ("level", "TRACE"),
        ("ts", "2026-07-13T13:41:00"),
    ],
)
def test_validate_pipeline_prefix__rejects_uncorrelated_structured_log_record(
    valid_pipeline: PipelinePaths,
    field: str,
    replacement: str,
) -> None:
    inventory = _document(valid_pipeline.inventory)
    run_id = inventory["run_id"]
    assert isinstance(run_id, str)
    structured_log = valid_pipeline.pipeline / ".docmend" / f"docmend-{run_id}.jsonl"
    record = {
        "ts": "2026-07-13T13:41:00+00:00",
        "level": "INFO",
        "run_id": run_id,
        "command": "scan",
        "event": "scan.completed",
    }
    record[field] = replacement
    structured_log.write_text(
        json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(QualificationIncomplete, match="scan structured log"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="scan")


def test_validate_pipeline_prefix__returns_raw_scan_conservation_failure(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.inventory)
    totals = _mapping(document["totals"])
    totals["files"] = COUNT - 1
    _write_document(valid_pipeline.inventory, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="scan")

    assert prefix.scanned_files == COUNT - 1
    assert prefix.public_failure == "conservation-mismatch"
    assert prefix.run_id
    assert prefix.artifact_bytes["inventory"] > 0
    assert prefix.artifact_bytes["structured-log"] > 0


def test_validate_pipeline_prefix__returns_raw_verify_finding_failure(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.verify_report)
    document["findings"] = []
    document["clean"] = True
    _write_document(valid_pipeline.verify_report, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.observed_findings == 0
    assert prefix.public_failure == "finding-mismatch"


def test_validate_pipeline_prefix__equal_aggregate_plan_mismatch_is_public_failure(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.plan)
    totals = _mapping(document["totals"])
    totals["actions"] = _integer(totals, "actions") - 1
    totals["skips"] = _integer(totals, "skips") + 1
    _write_document(valid_pipeline.plan, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="plan")

    assert prefix.public_failure == "conservation-mismatch"


def test_validate_pipeline_prefix__identity_failure_dominates_semantic_mismatch(
    valid_pipeline: PipelinePaths,
) -> None:
    inventory = _document(valid_pipeline.inventory)
    inventory_totals = _mapping(inventory["totals"])
    inventory_totals["files"] = COUNT - 1
    _write_document(valid_pipeline.inventory, inventory)
    plan = _document(valid_pipeline.plan)
    plan["generated_by"] = "docmend 9.9.9"
    _write_document(valid_pipeline.plan, plan)

    with pytest.raises(QualificationIncomplete, match="plan producer"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="plan")


def test_validate_pipeline_prefix__report_identity_dominates_conservation_mismatch(
    valid_pipeline: PipelinePaths,
) -> None:
    report = _document(valid_pipeline.report)
    totals = _mapping(report["totals"])
    outcomes = _mappings(report["outcomes"])
    totals["applied"] = _integer(totals, "applied") - 1
    totals["failed"] = 1
    first = outcomes[0]
    first["path"] = "synthetic/wrong-path.txt"
    _write_document(valid_pipeline.report, report)

    with pytest.raises(QualificationIncomplete, match="outcome binding"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")


def test_validate_pipeline_prefix__manifest_object_identity_mismatch_is_incomplete(
    valid_pipeline: PipelinePaths,
) -> None:
    plan = _document(valid_pipeline.plan)
    actions = _mappings(plan["actions"])
    rename = next(action for action in actions if action["operations"] == ["rename"])
    action_id = rename["action_id"]
    report, _digest = read_report_snapshot(valid_pipeline.report)
    manifest = valid_pipeline.pipeline / ".docmend" / f"docmend-{report.run_id}-manifest.jsonl"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    for index in range(1, len(lines)):
        record = _mapping(json.loads(lines[index]))
        if record["action_id"] != action_id:
            continue
        identity = _mapping(record["source_identity"])
        identity["ino"] = _integer(identity, "ino") + 1
        record["expected_published_identity"] = identity
        lines[index] = json.dumps(record, separators=(",", ":"), sort_keys=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_document = _document(valid_pipeline.report)
    report_document["manifest_sha256"] = _sha256(manifest)
    _write_document(valid_pipeline.report, report_document)

    with pytest.raises(QualificationIncomplete, match="published object identity"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")


def test_validate_pipeline_prefix__post_apply_object_replacement_is_incomplete(
    valid_pipeline: PipelinePaths,
) -> None:
    plan = _document(valid_pipeline.plan)
    action = _mappings(plan["actions"])[0]
    relative = action["target_path"] or action["path"]
    assert isinstance(relative, str)
    target = valid_pipeline.corpus / relative
    original = target.lstat()
    replacement = target.with_name(f".{target.name}.replacement")
    replacement.write_bytes(target.read_bytes())
    replacement.chmod(original.st_mode & 0o777)
    replacement.replace(target)
    current = target.lstat()
    assert (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)

    with pytest.raises(QualificationIncomplete, match="published object identity"):
        validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")


@pytest.mark.parametrize("mutation", ["offset", "would-apply"])
def test_validate_pipeline_prefix__exact_report_mismatch_is_public_failure(
    valid_pipeline: PipelinePaths,
    mutation: str,
) -> None:
    document = _document(valid_pipeline.report)
    totals = _mapping(document["totals"])
    if mutation == "offset":
        totals["applied"] = _integer(totals, "applied") - 1
        totals["skipped"] = 1
    else:
        totals["would_apply"] = 1
    _write_document(valid_pipeline.report, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="apply")

    assert prefix.public_failure == "conservation-mismatch"


def test_validate_pipeline_prefix__same_count_finding_substitution_is_public_failure(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.verify_report)
    findings = _mappings(document["findings"])
    finding = findings[0]
    finding["path"] = "synthetic/wrong-path.txt"
    _write_document(valid_pipeline.verify_report, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.public_failure == "finding-mismatch"


def test_verify__checked_count_must_match_corpus(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.verify_report)
    document["checked_files"] = COUNT - 1
    _write_document(valid_pipeline.verify_report, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.public_failure == "conservation-mismatch"
    with pytest.raises(QualificationFailure, match="conservation-mismatch"):
        reconcile_pipeline(valid_pipeline, count=COUNT)


def test_verify_findings__duplicate_is_not_collapsed(
    valid_pipeline: PipelinePaths,
) -> None:
    document = _document(valid_pipeline.verify_report)
    findings = _mappings(document["findings"])
    findings.append(dict(findings[0]))
    _write_document(valid_pipeline.verify_report, document)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.public_failure == "finding-mismatch"


def test_verification_finding_keys__is_sorted_and_duplicate_preserving(
    valid_pipeline: PipelinePaths,
) -> None:
    report = read_verify_report(valid_pipeline.verify_report)
    finding = report.findings[0]
    duplicated = report.model_copy(update={"findings": [finding, finding]})

    assert verification_finding_keys(duplicated) == (
        (finding.path, finding.check),
        (finding.path, finding.check),
    )


def test_boundary_oracle__requires_exact_final_target_bytes_and_encoding(
    valid_pipeline: PipelinePaths,
) -> None:
    recipe = boundary_samples(COUNT)[0]
    expected = expected_boundary_output(recipe)
    target = valid_pipeline.corpus / expected.path
    target.write_bytes(target.read_bytes() + b"corrupt")

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.public_failure == "conservation-mismatch"


def test_boundary_oracle__undefined_cp1252_byte_is_typed_conservation_failure(
    valid_pipeline: PipelinePaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from docmend import scale_reconcile

    recipe = next(
        recipe
        for recipe in boundary_samples(COUNT)
        if expected_boundary_output(recipe).encoding == "windows-1252"
    )
    original = scale_reconcile.expected_boundary_output
    invalid = b"\x81"

    def expected_with_undefined_byte(candidate: ScaleRecipe) -> ExpectedBoundaryOutput:
        expected = original(candidate)
        if candidate.path != recipe.path:
            return expected
        return replace(
            expected,
            data=invalid,
            sha256="sha256:" + hashlib.sha256(invalid).hexdigest(),
        )

    monkeypatch.setattr(scale_reconcile, "expected_boundary_output", expected_with_undefined_byte)
    expected = expected_with_undefined_byte(recipe)
    (valid_pipeline.corpus / expected.path).write_bytes(invalid)

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.public_failure == "conservation-mismatch"


def test_boundary_oracle__rejects_dangling_original_rename_entry(
    valid_pipeline: PipelinePaths,
) -> None:
    recipe = next(
        recipe
        for recipe in boundary_samples(COUNT)
        if expected_boundary_output(recipe).path != recipe.path
    )
    original = valid_pipeline.corpus / recipe.path
    assert not os.path.lexists(original)
    original.symlink_to("missing-after-rename")
    assert not original.exists()

    prefix = validate_pipeline_prefix(valid_pipeline, count=COUNT, through="verify")

    assert prefix.public_failure == "conservation-mismatch"
