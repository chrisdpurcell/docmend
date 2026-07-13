"""Default-gate source-tree scale contract for NFR-001."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from docmend.artifacts import (
    read_inventory,
    read_plan,
    read_report,
    read_verify_report,
    sha256_of_file,
)
from docmend.cli import app
from docmend.scale_corpus import (
    ScaleRecipeClass,
    boundary_samples,
    expected_boundary_output,
    expected_finding_keys,
    iter_recipes,
    materialize_scale_corpus,
    recipe_counts,
)
from docmend.scale_reconcile import verification_finding_keys

FILE_COUNT = 1_000
runner = CliRunner()


def test_pr_scale__full_pipeline_and_exact_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    corpus = tmp_path / "corpus"
    summary = materialize_scale_corpus(corpus, FILE_COUNT)
    counts = recipe_counts(FILE_COUNT)
    expected_inventory_paths: set[str] = set()
    expected_action_paths: set[str] = set()
    expected_noop_paths: set[str] = set()
    expected_skip_paths: set[str] = set()
    for recipe in iter_recipes(FILE_COUNT):
        expected_inventory_paths.add(recipe.path)
        if recipe.recipe_class is ScaleRecipeClass.CLEAN_MARKDOWN:
            expected_noop_paths.add(recipe.path)
        elif recipe.recipe_class is ScaleRecipeClass.BELOW_FLOOR_SKIP:
            expected_skip_paths.add(recipe.path)
        else:
            expected_action_paths.add(recipe.path)
    inventory = tmp_path / "inventory.json"
    plan = tmp_path / "plan.json"
    report = tmp_path / "report.json"
    verify_report = tmp_path / "verify-report.json"

    scanned = runner.invoke(app, ["scan", str(corpus), "--report", str(inventory)])
    assert scanned.exit_code == 0, scanned.output
    inventory_model = read_inventory(inventory)
    assert summary.count == FILE_COUNT
    assert summary.recipe_counts == counts
    assert len(expected_inventory_paths) == FILE_COUNT
    assert expected_action_paths.isdisjoint(expected_noop_paths)
    assert expected_action_paths.isdisjoint(expected_skip_paths)
    assert expected_noop_paths.isdisjoint(expected_skip_paths)
    assert expected_action_paths | expected_noop_paths | expected_skip_paths == (
        expected_inventory_paths
    )
    assert len(expected_action_paths) == counts.actions
    assert len(expected_noop_paths) == counts.noops
    assert len(expected_skip_paths) == counts.skips
    assert inventory_model.totals.files == FILE_COUNT
    assert len(inventory_model.files) == FILE_COUNT
    assert {record.path for record in inventory_model.files} == expected_inventory_paths
    assert inventory_model.totals.total_size_bytes == summary.file_bytes
    assert inventory_model.totals.symlinks == 0
    assert inventory_model.totals.skipped == 0
    assert inventory_model.totals.hard_link_groups == 0

    planned = runner.invoke(
        app,
        ["plan", "--inventory", str(inventory), "--out", str(plan)],
    )
    assert planned.exit_code == 0, planned.output
    plan_model = read_plan(plan)
    action_paths = {action.path for action in plan_model.actions}
    skip_reasons = {skip.path: skip.reason for skip in plan_model.skips}
    assert plan_model.totals.actions == counts.actions == len(plan_model.actions)
    assert plan_model.totals.skips == counts.skips == len(plan_model.skips)
    assert len(action_paths) == len(plan_model.actions)
    assert len(skip_reasons) == len(plan_model.skips)
    assert action_paths == expected_action_paths
    assert skip_reasons == dict.fromkeys(expected_skip_paths, "below-non-ascii-floor")
    assert expected_inventory_paths - action_paths - skip_reasons.keys() == expected_noop_paths
    assert counts.total == FILE_COUNT
    assert counts.actions + counts.skips + counts.noops == inventory_model.totals.files

    applied = runner.invoke(
        app,
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
    assert applied.exit_code == 0, applied.output
    report_model = read_report(report)
    assert report_model.totals.applied == counts.actions == len(report_model.outcomes)
    assert report_model.totals.would_apply == 0
    assert report_model.totals.skipped == 0
    assert report_model.totals.failed == 0
    assert report_model.totals.not_attempted == 0
    assert {outcome.action_id for outcome in report_model.outcomes} == {
        action.action_id for action in plan_model.actions
    }

    manifest = tmp_path / ".docmend" / f"docmend-{report_model.run_id}-manifest.jsonl"
    verified = runner.invoke(
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
    assert verified.exit_code == 1, verified.output
    verify_model = read_verify_report(verify_report)
    assert verify_model.checked_files == FILE_COUNT
    assert tuple(sorted(item.kind for item in verify_model.inputs)) == (
        "manifest",
        "plan",
        "report",
    )
    assert verify_model.clean is False
    assert verification_finding_keys(verify_model) == expected_finding_keys(FILE_COUNT)

    samples = boundary_samples(FILE_COUNT)
    assert {recipe.recipe_class for recipe in samples} == set(ScaleRecipeClass)
    for recipe in samples:
        expected = expected_boundary_output(recipe)
        target = corpus / expected.path
        data = target.read_bytes()
        assert data == expected.data, recipe.path
        assert sha256_of_file(target) == expected.sha256, recipe.path
        if expected.encoding == "utf-8":
            data.decode("utf-8")
        else:
            with pytest.raises(UnicodeDecodeError):
                data.decode("utf-8")
            data.decode("cp1252")
        if expected.path != recipe.path:
            assert not (corpus / recipe.path).exists(), recipe.path
