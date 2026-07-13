"""Apply safety gate (FR-005, OQ-005/adr-0004, OQ-035 risk tiers).

Pure independent predicates; every failing predicate refuses with exit 3
(mapped by the CLI). Pairwise coverage over the predicate space per §17.2
Operations row (allpairspy, t=3 for the preservation/manifest/backup trio).
"""

import os
from collections.abc import Sequence
from pathlib import Path

import pytest
from allpairspy import AllPairs  # pyright: ignore[reportMissingTypeStubs]

from docmend.config import DocmendConfig, RenameConfig
from docmend.plan import (
    ActionProvenance,
    ArtifactRef,
    Plan,
    PlanAction,
    PlanTotals,
    SkipDecision,
)
from docmend.scale_resources import (
    MANIFEST_BYTES_PER_ACTION,
    CapacityCheck,
    Requirement,
    group_capacity_by_filesystem,
)
from docmend.transform.dispatch import Operation
from docmend.writer import gate
from docmend.writer.gate import ApplyOptions, GateRefusal, evaluate_gate, is_content_rewrite

RUN = "run_20260706T000000Z_00008a"


def make_action(
    *,
    idx: int = 1,
    operations: Sequence[Operation],
    path: str,
    target_path: str | None,
    source_size_bytes: int = 10,
) -> PlanAction:
    """Mirror tests/test_plan_artifact.py's construction style for a single action."""
    return PlanAction(
        action_id=f"{RUN}/a{idx}",
        docmend_id=f"01980000-0000-7000-8000-{idx:012d}",
        path=path,
        source_sha256="sha256:" + "a" * 64,
        source_size_bytes=source_size_bytes,
        operations=list(operations),
        target_path=target_path,
        provenance=ActionProvenance(detected_encoding=None, newline_style="lf"),
    )


def make_plan(actions: list[PlanAction], config: DocmendConfig | None = None) -> Plan:
    """Mirror tests/test_plan_artifact.py's construction style for a whole plan."""
    return Plan(
        run_id=RUN,
        generated_at="2026-07-06T00:00:00+00:00",
        generated_by="docmend 0.1.0",
        inventory_ref=ArtifactRef(path="inv.json", run_id=RUN, sha256="sha256:" + "0" * 64),
        config=(config or DocmendConfig()).model_dump(mode="json"),
        actions=actions,
        skips=[],
        totals=PlanTotals(actions=len(actions), skips=0),
    )


def rename_only_plan() -> Plan:
    """Plan (a): a single rename-only action — OQ-035's undoable-from-manifest tier."""
    return make_plan([make_action(operations=["rename"], path="a.txt", target_path="a.md")])


def single_rewrite_plan() -> Plan:
    """Plan (b): a single content-rewrite action, no rename."""
    return make_plan(
        [make_action(operations=["normalize_newlines"], path="b.txt", target_path=None)]
    )


def multi_rewrite_plan() -> Plan:
    """Plan (c): three content-rewrite actions."""
    return make_plan(
        [
            make_action(
                idx=i, operations=["normalize_newlines"], path=f"c{i}.txt", target_path=None
            )
            for i in (1, 2, 3)
        ]
    )


def no_op_options() -> ApplyOptions:
    return ApplyOptions(write=True, backup_root=None, preserved_by=None, allow_no_backup=False)


class TestIsContentRewrite:
    def test_rename_only_action__is_not_content_rewrite(self) -> None:
        action = make_action(operations=["rename"], path="a.txt", target_path="a.md")
        assert is_content_rewrite(action) is False

    def test_rewrite_action__is_content_rewrite(self) -> None:
        action = make_action(operations=["normalize_newlines"], path="b.txt", target_path=None)
        assert is_content_rewrite(action) is True


class TestPreservationPredicate:
    def test_content_rewrite_without_strategy__refused(self, tmp_path: Path) -> None:
        """FR-005 acceptance: an unpreserved content rewrite exits non-zero, writes nothing."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )
        assert len(refusals) == 1
        assert refusals[0].predicate == "preservation"

    def test_content_rewrite_with_backup_dir__passes(self, tmp_path: Path) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        options = ApplyOptions(
            write=True,
            backup_root=tmp_path / "backups",
            preserved_by=None,
            allow_no_backup=False,
        )
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals == []

    def test_content_rewrite_with_declared_preservation__passes(self, tmp_path: Path) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        options = ApplyOptions(
            write=True, backup_root=None, preserved_by="git", allow_no_backup=False
        )
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals == []

    def test_single_action_opt_in__passes(self, tmp_path: Path) -> None:
        """FR-005 low-risk opt-in; NFR-006/G-006."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        options = ApplyOptions(
            write=True, backup_root=None, preserved_by=None, allow_no_backup=True
        )
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals == []

    def test_multi_action_opt_in__refused(self, tmp_path: Path) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        options = ApplyOptions(
            write=True, backup_root=None, preserved_by=None, allow_no_backup=True
        )
        refusals = evaluate_gate(
            multi_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )
        # allow_no_backup on a multi-action plan is out of scope for the opt-in
        # AND the plan still has no active strategy, so both preservation
        # sub-checks fire; every refusal produced is predicate "preservation".
        assert refusals
        assert {r.predicate for r in refusals} == {"preservation"}
        assert any("limited to single-action plans" in r.message for r in refusals)

    def test_rename_only_plan__needs_no_strategy(self, tmp_path: Path) -> None:
        """OQ-035 risk tier: manifest suffices for pure path moves."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        refusals = evaluate_gate(
            rename_only_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals == []

    def test_manifest_only_configuration__does_not_satisfy_preservation(
        self, tmp_path: Path
    ) -> None:
        """FR-005 acceptance criterion, verbatim case: manifest alone never preserves bytes."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        refusals = evaluate_gate(
            multi_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )
        assert any(r.predicate == "preservation" for r in refusals)


class TestContainmentBelt:
    def test_backup_dir_inside_target__refused_and_nothing_created(self, tmp_path: Path) -> None:
        """codex CR-002: a refusal must not mkdir a backup destination inside the library."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        (source_root / "a.txt").write_text("hello")
        backup_root = source_root / "backups"
        assert not backup_root.exists()
        before = sorted(str(p.relative_to(source_root)) for p in source_root.rglob("*"))

        options = ApplyOptions(
            write=True, backup_root=backup_root, preserved_by=None, allow_no_backup=False
        )
        refusals = evaluate_gate(
            rename_only_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )

        assert any(r.predicate == "backup-outside-target" for r in refusals)
        assert not backup_root.exists()
        after = sorted(str(p.relative_to(source_root)) for p in source_root.rglob("*"))
        assert before == after

    def test_containment_belt__escaping_target_refused(self, tmp_path: Path) -> None:
        """Belt over the model validators (§8.5/§13.5): a crafted artifact must still refuse."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        escaping_action = PlanAction.model_construct(
            action_id=f"{RUN}/a1",
            docmend_id="01980000-0000-7000-8000-000000000001",
            path="ok.md",
            source_sha256="sha256:" + "a" * 64,
            source_size_bytes=10,
            operations=["rename"],
            target_path="../escape.md",
            provenance=ActionProvenance(detected_encoding=None, newline_style="lf"),
        )
        plan = make_plan([escaping_action])

        refusals = evaluate_gate(
            plan,
            DocmendConfig(),
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )

        assert any(r.predicate == "containment" for r in refusals)


class TestWritabilityProbes:
    def test_backup_dir_unwritable__refused(self, tmp_path: Path) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        backup_root = tmp_path / "backups"
        backup_root.mkdir()
        backup_root.chmod(0o500)
        try:
            options = ApplyOptions(
                write=True, backup_root=backup_root, preserved_by=None, allow_no_backup=False
            )
            refusals = evaluate_gate(
                rename_only_plan(),
                DocmendConfig(),
                source_root=source_root,
                options=options,
                manifest_dir=tmp_path / "manifest",
            )
            assert any(r.predicate == "backup-writable" for r in refusals)
        finally:
            backup_root.chmod(0o700)

    def test_manifest_dir_unwritable__refused(self, tmp_path: Path) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        manifest_dir = tmp_path / "manifest"
        manifest_dir.mkdir()
        manifest_dir.chmod(0o500)
        try:
            refusals = evaluate_gate(
                rename_only_plan(),
                DocmendConfig(),
                source_root=source_root,
                options=no_op_options(),
                manifest_dir=manifest_dir,
            )
            assert any(r.predicate == "manifest-writable" for r in refusals)
        finally:
            manifest_dir.chmod(0o700)


class TestDiskPreflight:
    def test_grouping__sums_shared_mount_once_and_keeps_distinct_mounts_separate(self) -> None:
        requirements = (
            Requirement(path=Path("/source"), bytes=300, inodes=1),
            Requirement(path=Path("/backup"), bytes=100, inodes=2),
            Requirement(path=Path("/artifacts"), bytes=50, inodes=4),
        )
        devices = {Path("/source"): 7, Path("/backup"): 7, Path("/artifacts"): 9}

        def fake_stat(path: Path) -> os.stat_result:
            return os.stat_result((0, 0, devices[path], 0, 0, 0, 0, 0, 0, 0))

        groups = group_capacity_by_filesystem(
            requirements,
            stat_path=fake_stat,
        )

        assert [(group.required_bytes, group.required_inodes) for group in groups] == [
            (400, 3),
            (50, 4),
        ]

    def test_gate__groups_backup_staging_and_artifact_allowances_on_shared_mount(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        backup_root = tmp_path / "backups"
        manifest_dir = tmp_path / "manifest"
        captured: list[Requirement] = []

        def fail_shared_capacity(requirements: Sequence[Requirement]) -> CapacityCheck:
            captured.extend(requirements)

            def same_device(_path: Path) -> os.stat_result:
                return os.stat_result((0, 0, 11, 0, 0, 0, 0, 0, 0, 0))

            groups = group_capacity_by_filesystem(
                requirements,
                stat_path=same_device,
            )
            assert len(groups) == 1
            assert groups[0].required_bytes == sum(item.bytes for item in requirements)
            return CapacityCheck(ok=False, filesystems=())

        monkeypatch.setattr(gate, "check_capacity", fail_shared_capacity)
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=ApplyOptions(
                write=True,
                backup_root=backup_root,
                preserved_by=None,
                allow_no_backup=False,
            ),
            manifest_dir=manifest_dir,
        )

        assert [refusal.predicate for refusal in refusals].count("disk-preflight") == 1
        assert {item.path for item in captured} == {source_root, backup_root, manifest_dir}
        assert len(captured) == 7
        assert sum(item.inodes for item in captured) == 10

    def test_gate__reserves_custom_report_parent_directories_and_keeps_refusal_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        manifest_dir = tmp_path / "manifest"
        captured: list[Requirement] = []

        def fail_capacity(requirements: Sequence[Requirement]) -> CapacityCheck:
            captured.extend(requirements)
            return CapacityCheck(ok=False, filesystems=())

        monkeypatch.setattr(gate, "check_capacity", fail_capacity)
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=manifest_dir,
            report_path=tmp_path / "nested" / "reports" / "report.json",
        )

        assert [refusal.predicate for refusal in refusals] == [
            "preservation",
            "disk-preflight",
        ]
        report_requirements = [item for item in captured if item.path == tmp_path]
        assert sum(item.inodes for item in report_requirements) == 4

    def test_gate__artifact_allowance_counts_actions_and_plan_skips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        manifest_dir = tmp_path / "manifest"
        skips = [
            SkipDecision(path=f"skip-{index}.txt", reason="excluded", detail=None)
            for index in range(9)
        ]
        plan = single_rewrite_plan().model_copy(
            update={"skips": skips, "totals": PlanTotals(actions=0, skips=0)}
        )
        captured: list[Requirement] = []

        def capture_capacity(requirements: Sequence[Requirement]) -> CapacityCheck:
            captured.extend(requirements)
            return CapacityCheck(ok=True, filesystems=())

        monkeypatch.setattr(gate, "check_capacity", capture_capacity)
        assert (
            evaluate_gate(
                plan,
                DocmendConfig(),
                source_root=source_root,
                options=ApplyOptions(
                    write=True,
                    backup_root=None,
                    preserved_by="external",
                    allow_no_backup=False,
                ),
                manifest_dir=manifest_dir,
            )
            == []
        )

        artifact_requirements = [item for item in captured if item.path == manifest_dir]
        assert max(item.bytes for item in artifact_requirements) >= MANIFEST_BYTES_PER_ACTION * 10

    def test_gate__overwrite_target_probe_race_becomes_disk_refusal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()
        target = source_root / "existing.md"
        target.write_text("existing", encoding="utf-8")
        action = make_action(
            operations=["normalize_newlines"],
            path="source.txt",
            target_path="existing.md",
        )
        config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
        real_stat = Path.stat

        def racing_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
            if path == target:
                raise PermissionError("synthetic target race")
            return real_stat(path, follow_symlinks=follow_symlinks)

        monkeypatch.setattr(Path, "stat", racing_stat)
        refusals = evaluate_gate(
            make_plan([action], config=config),
            config,
            source_root=source_root,
            options=ApplyOptions(
                write=True,
                backup_root=tmp_path / "backups",
                preserved_by=None,
                allow_no_backup=False,
            ),
            manifest_dir=tmp_path / "manifest",
        )

        assert any(
            refusal.predicate == "disk-preflight"
            and "overwrite target capacity probe failed" in refusal.message
            for refusal in refusals
        )

    def test_gate__invalid_fragment_size_becomes_disk_refusal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_root = tmp_path / "root"
        source_root.mkdir()

        def invalid_statvfs(_path: Path) -> os.statvfs_result:
            return os.statvfs_result((4096, 0, 1, 1, 1, 1, 1, 1, 0, 255))

        monkeypatch.setattr(gate.os, "statvfs", invalid_statvfs)
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=ApplyOptions(
                write=True,
                backup_root=tmp_path / "backups",
                preserved_by=None,
                allow_no_backup=False,
            ),
            manifest_dir=tmp_path / "manifest",
        )

        assert any(
            refusal.predicate == "disk-preflight"
            and "fragment-size probe failed" in refusal.message
            for refusal in refusals
        )

    def test_disk_preflight__refused_when_backup_mount_too_small(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OQ-005: a backup mount without room for the planned copies must refuse."""
        source_root = tmp_path / "root"
        source_root.mkdir()

        def fail_capacity(_requirements: Sequence[Requirement]) -> CapacityCheck:
            return CapacityCheck(ok=False, filesystems=())

        monkeypatch.setattr(gate, "check_capacity", fail_capacity)
        options = ApplyOptions(
            write=True,
            backup_root=tmp_path / "backups",
            preserved_by=None,
            allow_no_backup=False,
        )
        refusals = evaluate_gate(
            single_rewrite_plan(),
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )
        assert any(r.predicate == "disk-preflight" for r in refusals)

    def test_disk_preflight__counts_overwrite_targets_and_output_growth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """codex CR-006: overwrite backups count the clobbered target; growth is bounded."""
        # Sub-case 1: overwrite policy backs up the live-colliding target too,
        # so free space covering only the sources (not sources + target) refuses.
        source_root = tmp_path / "root"
        source_root.mkdir()
        target = source_root / "existing.md"
        target.write_bytes(b"x" * 100)
        action = make_action(
            operations=["normalize_newlines"],
            path="src.txt",
            target_path="existing.md",
            source_size_bytes=10,
        )
        plan = make_plan(
            [action], config=DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
        )
        backup_root = tmp_path / "backups"

        captured: list[Requirement] = []

        def capture_capacity(requirements: Sequence[Requirement]) -> CapacityCheck:
            captured.extend(requirements)
            return CapacityCheck(ok=True, filesystems=())

        monkeypatch.setattr(gate, "check_capacity", capture_capacity)
        options = ApplyOptions(
            write=True, backup_root=backup_root, preserved_by=None, allow_no_backup=False
        )
        refusals = evaluate_gate(
            plan,
            DocmendConfig(rename=RenameConfig(on_collision="overwrite")),
            source_root=source_root,
            options=options,
            manifest_dir=tmp_path / "manifest",
        )
        assert not any(r.predicate == "disk-preflight" for r in refusals)
        [backup_requirement] = [item for item in captured if item.path == backup_root]
        assert backup_requirement.inodes > 2
        assert backup_requirement.bytes >= 110

        # Sub-case 2: single-action plan, free space covers the source size but
        # not the re-encode growth bound (source_size * 3).
        source_root_2 = tmp_path / "root2"
        source_root_2.mkdir()
        growth_action = make_action(
            operations=["reencode"], path="g.txt", target_path=None, source_size_bytes=100
        )
        growth_plan = make_plan([growth_action])

        captured.clear()
        growth_options = ApplyOptions(
            write=True, backup_root=None, preserved_by=None, allow_no_backup=True
        )
        growth_refusals = evaluate_gate(
            growth_plan,
            DocmendConfig(),
            source_root=source_root_2,
            options=growth_options,
            manifest_dir=tmp_path / "manifest2",
        )
        assert not any(r.predicate == "disk-preflight" for r in growth_refusals)
        [staging_requirement] = [item for item in captured if item.path == source_root_2]
        assert staging_requirement.inodes == 1
        assert staging_requirement.bytes >= 300


class TestOverwritePreservation:
    def test_overwrite_policy_with_live_collision__requires_strategy(self, tmp_path: Path) -> None:
        """G-002: an overwrite that would destroy an existing target needs a strategy."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        (source_root / "existing.md").write_text("old content")
        action = make_action(
            operations=["normalize_newlines"], path="src.txt", target_path="existing.md"
        )
        config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
        plan = make_plan([action], config=config)

        refusals = evaluate_gate(
            plan,
            config,
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )
        assert any(r.predicate == "overwrite-preservation" for r in refusals)

        options_declared = ApplyOptions(
            write=True, backup_root=None, preserved_by="external", allow_no_backup=False
        )
        refusals_declared = evaluate_gate(
            plan,
            config,
            source_root=source_root,
            options=options_declared,
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals_declared == []

    def test_overwrite_policy_without_live_collision__passes(self, tmp_path: Path) -> None:
        """Overwrite collision policy alone is not the trigger — an actual clobber is (G-002)."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        action = make_action(operations=["rename"], path="src.txt", target_path="new.md")
        config = DocmendConfig(rename=RenameConfig(on_collision="overwrite"))
        plan = make_plan([action], config=config)

        refusals = evaluate_gate(
            plan,
            config,
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals == []


class TestEmptyPlan:
    def test_empty_plan__gate_passes(self, tmp_path: Path) -> None:
        """A plan with no actions is a degenerate no-op for every predicate."""
        source_root = tmp_path / "root"
        source_root.mkdir()
        refusals = evaluate_gate(
            make_plan([]),
            DocmendConfig(),
            source_root=source_root,
            options=no_op_options(),
            manifest_dir=tmp_path / "manifest",
        )
        assert refusals == []


PRESERVATION = ["none", "backup_dir", "preserved_by", "opt_in"]
PLAN_SHAPE = ["single_rewrite", "multi_rewrite", "single_rename_only"]
MANIFEST_DIR = ["writable", "unwritable"]
BACKUP_DEST = ["outside", "inside_target", "unwritable"]


@pytest.mark.parametrize(
    "preservation,plan_shape,manifest_dir,backup_dest",
    list(AllPairs([PRESERVATION, PLAN_SHAPE, MANIFEST_DIR, BACKUP_DEST], n=3)),
)
def test_gate_pairwise__every_failing_predicate_refuses(
    tmp_path: Path, preservation: str, plan_shape: str, manifest_dir: str, backup_dest: str
) -> None:
    """§17.2 Operations row: t=3 pairwise over the preservation/manifest/backup trio."""
    source_root = tmp_path / "root"
    source_root.mkdir()

    plan = {
        "single_rewrite": single_rewrite_plan,
        "multi_rewrite": multi_rewrite_plan,
        "single_rename_only": rename_only_plan,
    }[plan_shape]()
    has_content_rewrite = any(is_content_rewrite(a) for a in plan.actions)
    is_multi_action = len(plan.actions) > 1

    # backup_dest is only wired when preservation == "backup_dir"; otherwise
    # backup_root stays None and no backup refusal is possible.
    backup_root: Path | None = None
    cleanup_dirs: list[Path] = []
    if preservation == "backup_dir":
        if backup_dest == "outside":
            backup_root = tmp_path / "backups_outside"
        elif backup_dest == "inside_target":
            backup_root = source_root / "backups_inside"
        else:  # "unwritable"
            backup_root = tmp_path / "backups_unwritable"
            backup_root.mkdir()
            backup_root.chmod(0o500)
            cleanup_dirs.append(backup_root)

    manifest_path = tmp_path / "manifest"
    if manifest_dir == "unwritable":
        manifest_path.mkdir()
        manifest_path.chmod(0o500)
        cleanup_dirs.append(manifest_path)

    options = ApplyOptions(
        write=True,
        backup_root=backup_root,
        preserved_by="git" if preservation == "preserved_by" else None,
        allow_no_backup=preservation == "opt_in",
    )

    try:
        refusals = evaluate_gate(
            plan,
            DocmendConfig(),
            source_root=source_root,
            options=options,
            manifest_dir=manifest_path,
        )

        # Independently derived expectation (no re-derivation from gate internals):
        expected: set[str] = set()
        if has_content_rewrite and (
            preservation == "none" or (preservation == "opt_in" and is_multi_action)
        ):
            expected.add("preservation")
        if preservation == "backup_dir" and backup_dest == "inside_target":
            expected.add("backup-outside-target")
        if preservation == "backup_dir" and backup_dest == "unwritable":
            expected.add("backup-writable")
        if manifest_dir == "unwritable":
            expected.add("manifest-writable")

        assert {r.predicate for r in refusals} == expected
    finally:
        for d in cleanup_dirs:
            d.chmod(0o700)


def test_apply_options_and_gate_refusal__are_frozen_dataclasses() -> None:
    """Interface contract for Task 10: both types are immutable value objects."""
    options = no_op_options()
    with pytest.raises(AttributeError):
        options.write = False  # type: ignore[misc]

    refusal = GateRefusal(predicate="preservation", message="x")
    with pytest.raises(AttributeError):
        refusal.predicate = "other"  # type: ignore[misc]
