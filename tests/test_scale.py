"""NFR-001 scale test — 100k-file synthetic corpus, bounded memory (§19 MS-5 item 1).

The corpus is generated at test time from the recorded corpus.py seed into
tmp_path and never committed (OQ-032, adr-0015). The whole pipeline —
scan -> plan -> gate -> apply --write (preserved-by external) — runs
in-process via the library API (the tests/test_apply.py e2e idiom) so
tracemalloc can observe its allocations.

Opt-in only: requires BOTH `-m slow` and DOCMEND_SCALE=1, so default runs and
the standard-owned CI workflow skip it untouched. DOCMEND_SCALE_COUNT scales
the corpus (default 100_000) for cheaper local iterations.
"""

import logging
import os
import time
import tracemalloc
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from tests.helpers.writectx import apply_safety

from corpus import FileRecipe, materialize, seeded_faker
from docmend import discovery, planning
from docmend.artifacts import sha256_of_file
from docmend.config import DocmendConfig
from docmend.plan import ArtifactRef, Plan
from docmend.writer.apply import execute_plan
from docmend.writer.gate import ApplyOptions

SCAN_RUN_ID = "run_20260707T000000Z_00005a"
PLAN_RUN_ID = "run_20260707T000000Z_00005b"
APPLY_RUN_ID = "run_20260707T000000Z_00005c"
GENERATED_AT = "2026-07-07T00:00:00+00:00"

CORPUS_COUNT = int(os.environ.get("DOCMEND_SCALE_COUNT", "100000"))

# NFR-001 memory bound. The inventory, plan, and report are held in memory BY
# DESIGN (DR-001..DR-003 are whole-run artifacts), so the bound scales with
# file COUNT, not corpus BYTES — per-file content is streamed and dropped
# (discovery reads in chunks; plan/apply read one file at a time). Measured
# 2026-07-07 on the dev workstation (Fedora 44 / Linux 7.0, Intel Core Ultra 7
# 155H, Python 3.14.6, tmp_path on tmpfs — irrelevant to the metric, which is
# Python-heap-only): a 100,000-file run peaked at 477.4 MiB traced
# (~4.9 KiB/file; generate 2.6 s, scan 188.1 s, plan 18.3 s, apply 147.5 s,
# tracemalloc overhead included). The in-process test over-counts the real
# CLI, where each stage is its own process and only that stage's artifact is
# live. 10 KiB/file budget -> ~1041 MiB ceiling at 100k, ~2.2x measured.
MEMORY_BASE_BUDGET = 64 * 1024 * 1024  # interpreter noise floor for tiny counts
MEMORY_PER_FILE_BUDGET = 10 * 1024  # bytes of traced peak allowed per corpus file

# Deterministic variety mix, keyed on index % 40 (values are 2.5% slices):
# 60% utf-8 lf .txt (rename-only), 20% utf-8 crlf .txt (normalize+rename),
# 10% clean utf-8 lf .md (no-op by construction — FR-017's third state),
# 5% utf-8 crlf .md (normalize rewrite), 2.5% windows-1252 crlf .txt with
# enough non-ASCII to clear the OQ-030 floor (reencode path), 2.5%
# windows-1252 with sentences=1 (lands under encoding.non_ascii_floor=20 and
# exercises the plan-time skip ladder at scale).
_CLEAN_BUCKETS = frozenset(range(32, 36))


def _recipe(index: int) -> FileRecipe:
    # 53 x 41 nested shard dirs (co-prime with the 40 buckets so every shard
    # holds a mix), ~46 files each at 100k.
    shard = f"lib/{index % 53:02d}/{(index // 53) % 41:02d}"
    bucket = index % 40
    if bucket < 24:
        return FileRecipe(f"{shard}/doc{index:06d}.txt", "utf-8", "lf", sentences=1)
    if bucket < 32:
        return FileRecipe(f"{shard}/doc{index:06d}.txt", "utf-8", "crlf", sentences=1)
    if bucket < 36:
        return FileRecipe(f"{shard}/doc{index:06d}.md", "utf-8", "lf", sentences=1)
    if bucket < 38:
        return FileRecipe(f"{shard}/doc{index:06d}.md", "utf-8", "crlf", sentences=1)
    if bucket == 38:
        return FileRecipe(f"{shard}/doc{index:06d}.txt", "windows-1252", "crlf", sentences=8)
    return FileRecipe(f"{shard}/doc{index:06d}.txt", "windows-1252", "lf", sentences=1)


@pytest.fixture
def quiet_structlog() -> Iterator[None]:
    """Silence per-file DEBUG events. Unconfigured structlog prints everything;
    at 100k files that is ~200k rendered lines whose cost would swamp the run
    and belongs to the harness, not to the pipeline being measured."""
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    yield
    structlog.reset_defaults()


def _spot_verify(root: Path, plan: Plan, outcome_sha_by_action: dict[str, str]) -> None:
    """Read-only spot check over a sample of applied actions (§18.4 posture):
    the published file exists at its final path, hashes to the reported
    after_sha256, decodes as strict UTF-8, and carries no CR bytes."""
    sample = plan.actions[:: max(1, len(plan.actions) // 25)]
    assert sample
    for action in sample:
        final_rel = action.target_path if action.target_path is not None else action.path
        final = root / final_rel
        assert final.is_file(), final_rel
        if action.target_path is not None:
            assert not (root / action.path).exists(), action.path
        data = final.read_bytes()
        assert sha256_of_file(final) == outcome_sha_by_action[action.action_id]
        data.decode("utf-8")  # strict; raises on any non-UTF-8 residue
        assert b"\r" not in data, final_rel


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("DOCMEND_SCALE"),
    reason="NFR-001 scale test: set DOCMEND_SCALE=1 (materializes ~100k files, runs minutes)",
)
def test_scale_corpus__pipeline_totals_and_bounded_memory(
    tmp_path: Path, quiet_structlog: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MS-5 item 1: scan/plan/apply a seeded 100k-file corpus; assert artifact
    totals reconcile end-to-end and traced peak memory stays under the
    count-proportional NFR-001 budget."""
    root = tmp_path / "library"
    recipes = [_recipe(index) for index in range(CORPUS_COUNT)]
    clean_total = sum(1 for index in range(CORPUS_COUNT) if index % 40 in _CLEAN_BUCKETS)
    t0 = time.perf_counter()
    # materialize() is the corpus.py disk adapter: renders and writes one file
    # per loop iteration, so corpus BYTES never accumulate in memory.
    materialize(root, recipes, seeded_faker())
    del recipes
    t_gen = time.perf_counter()

    config = DocmendConfig()
    # Measurement starts after generation: NFR-001 bounds the pipeline, not
    # the test's own corpus factory.
    tracemalloc.start()

    inventory = discovery.scan(root, config, run_id=SCAN_RUN_ID, generated_at=GENERATED_AT)
    t_scan = time.perf_counter()
    assert inventory.totals.files == CORPUS_COUNT
    assert inventory.totals.symlinks == 0
    assert inventory.totals.skipped == 0

    inventory_ref = ArtifactRef(path="inv.json", run_id=SCAN_RUN_ID, sha256="sha256:" + "0" * 64)
    plan = planning.build_plan(
        inventory,
        config,
        run_id=PLAN_RUN_ID,
        generated_at=GENERATED_AT,
        inventory_ref=inventory_ref,
    )
    t_plan = time.perf_counter()
    # Conservation: every scanned file is an action, a skip, or a clean no-op
    # (FR-017's third state) — and the no-ops are exactly the clean .md slice.
    assert plan.totals.actions == len(plan.actions)
    assert plan.totals.skips == len(plan.skips)
    assert plan.totals.actions + plan.totals.skips == CORPUS_COUNT - clean_total

    options = ApplyOptions(
        write=True, backup_root=None, preserved_by="external", allow_no_backup=False
    )
    source_root = Path(plan.source_root or "")
    manifest_path = tmp_path / "manifest.jsonl"
    with apply_safety(
        plan,
        options=options,
        manifest_path=manifest_path,
        report_path=tmp_path / "report.json",
        run_id=APPLY_RUN_ID,
        state_dir=tmp_path / "state",
        monkeypatch=monkeypatch,
    ) as safety:
        report = execute_plan(
            run_id=APPLY_RUN_ID,
            manifest_path=manifest_path,
            started_at=GENERATED_AT,
            safety=safety,
        )
    t_apply = time.perf_counter()

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Applied count == planned actions; nothing skipped or failed at apply time.
    assert report.totals.applied == plan.totals.actions
    assert report.totals.skipped == 0
    assert report.totals.failed == 0
    assert report.totals.would_apply == 0
    assert len(report.outcomes) == plan.totals.actions
    with manifest_path.open("rb") as fh:
        # Manifest 2.0 shape (adr-0019): one header line plus an
        # intent+terminal pair per applied action (DMR-08 escrow — the scale
        # contract itself is sub-project 2; this keeps the lane runnable).
        assert sum(1 for _ in fh) == 1 + 2 * report.totals.applied

    outcome_sha_by_action = {
        o.action_id: o.after_sha256 for o in report.outcomes if o.after_sha256 is not None
    }
    assert len(outcome_sha_by_action) == report.totals.applied
    _spot_verify(source_root, plan, outcome_sha_by_action)

    ceiling = MEMORY_BASE_BUDGET + MEMORY_PER_FILE_BUDGET * CORPUS_COUNT
    print(
        f"\n[scale] files={CORPUS_COUNT} actions={plan.totals.actions} "
        f"skips={plan.totals.skips} clean={clean_total} applied={report.totals.applied}\n"
        f"[scale] generate={t_gen - t0:.1f}s scan={t_scan - t_gen:.1f}s "
        f"plan={t_plan - t_scan:.1f}s apply={t_apply - t_plan:.1f}s\n"
        f"[scale] tracemalloc peak={peak / 2**20:.1f} MiB ceiling={ceiling / 2**20:.1f} MiB"
    )
    assert peak < ceiling, (
        f"traced peak {peak / 2**20:.1f} MiB exceeds the NFR-001 budget "
        f"{ceiling / 2**20:.1f} MiB for {CORPUS_COUNT} files — memory no longer "
        "scales with file count alone"
    )
