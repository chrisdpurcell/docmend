"""Manifest chain reading and lifecycle reduction (adr-0019; Plan B Tasks 3-4).

`read_manifest_chain` orders validated sets by their prior_manifest_sha256
hash links — never caller order — and proves cross-set coherence: one root,
no forks/gaps, one plan, apply-before-restore, undoes lineage, the cross-set
transition table, terminal closure of dangling intents (review CR-NEW-002),
and the attempt-lineage invariants (CR-006). `reduce_lifecycle` then folds
the chain into one state per ORIGINAL apply action.

Fixture identity model (mirrors production): action_ids are minted by the
PLAN run (the helpers' RUN_ID) and stay immutable across re-executions by
later apply runs; restore INVERSE records mint their own action_ids in the
restore run's namespace and point back via undoes_action_id.
"""

import json
from pathlib import Path

import pytest
from tests.helpers.manifest2 import (
    RUN_ID as PLAN_RUN,
)
from tests.helpers.manifest2 import (
    SHA_C,
    header_doc,
    record_doc,
    write_set,
)

from docmend.artifacts import ArtifactError
from docmend.writer.manifest import (
    manifest_sha256,
    read_manifest_chain,
    reduce_lifecycle,
)

RUN_1 = "run_20260711T000000Z_000001"
RUN_2 = "run_20260711T000000Z_000002"
RUN_3 = "run_20260711T000000Z_000003"
RUN_4 = "run_20260711T000000Z_000004"

A1 = f"{PLAN_RUN}/a1"
A2 = f"{PLAN_RUN}/a2"
A3 = f"{PLAN_RUN}/a3"


def _record(
    run_id: str, action_seq: int, *, seq: int, result: str, **overrides: object
) -> dict[str, object]:
    doc = record_doc(action_seq, result=result, seq=seq, **overrides)
    doc["run_id"] = run_id  # the RECORDING run; action_id stays plan-minted
    return doc


def _inverse(
    run_id: str,
    undoes: str,
    inverse_seq: int,
    *,
    seq: int,
    result: str,
    undoes_run: str,
) -> dict[str, object]:
    """A restore inverse record: its OWN action_id lives in the restore run's
    namespace (as restore.py mints them); undoes_* names the apply action."""
    source_seq = int(undoes.rsplit("a", 1)[-1])
    doc = _record(run_id, source_seq, seq=seq, result=result)
    doc["action_id"] = f"{run_id}/a{inverse_seq}"
    doc["undoes_action_id"] = undoes
    doc["undoes_run_id"] = undoes_run
    return doc


def _apply_set(
    path: Path,
    run_id: str,
    *records: dict[str, object],
    prior: Path | None = None,
    prior_attempt: dict[str, object] | None = None,
    **header_overrides: object,
) -> Path:
    header = header_doc(run_id=run_id, **header_overrides)
    if prior is not None:
        prior_sha = manifest_sha256(prior)
        header["prior_manifest_sha256"] = prior_sha
        header["prior_attempt"] = prior_attempt or {
            "run_id": json.loads(prior.read_text().splitlines()[0])["run_id"],
            "report_sha256": None,
            "manifest_sha256": prior_sha,
        }
    elif prior_attempt is not None:
        header["prior_attempt"] = prior_attempt
    return write_set(path, header, *records)


def _pair(run_id: str, action_seq: int, *, base_seq: int) -> list[dict[str, object]]:
    """One action's intent+applied pair recorded by `run_id`."""
    intent = _record(run_id, action_seq, seq=base_seq, result="intent")
    terminal = _record(run_id, action_seq, seq=base_seq + 1, result="applied")
    return [intent, terminal]


def _worked_example(tmp_path: Path) -> list[Path]:
    """The design's worked example: M1 (a1 done, a2 dangling intent), M2
    (a2 adjudicated never-happened and re-executed, a3 done), M3 (restore:
    a3 undone, a2 inverse dangling), M4 (a2 inverse closed, a1 undone)."""
    m1 = _apply_set(
        tmp_path / "m1.jsonl",
        RUN_1,
        *_pair(RUN_1, 1, base_seq=1),
        _record(RUN_1, 2, seq=3, result="intent"),
    )
    m2 = _apply_set(
        tmp_path / "m2.jsonl",
        RUN_2,
        *_pair(RUN_2, 2, base_seq=1),
        *_pair(RUN_2, 3, base_seq=3),
        prior=m1,
    )
    m3 = _apply_set(
        tmp_path / "m3.jsonl",
        RUN_3,
        _inverse(RUN_3, A3, 1, seq=1, result="intent", undoes_run=RUN_2),
        _inverse(RUN_3, A3, 1, seq=2, result="applied", undoes_run=RUN_2),
        _inverse(RUN_3, A2, 2, seq=3, result="intent", undoes_run=RUN_2),
        prior=m2,
        kind="restore",
    )
    m4_closure = _inverse(RUN_4, A2, 2, seq=1, result="applied", undoes_run=RUN_2)
    m4_closure["action_id"] = f"{RUN_3}/a2"  # closes M3's dangling inverse intent
    m4 = _apply_set(
        tmp_path / "m4.jsonl",
        RUN_4,
        m4_closure,
        _inverse(RUN_4, A1, 2, seq=2, result="intent", undoes_run=RUN_1),
        _inverse(RUN_4, A1, 2, seq=3, result="applied", undoes_run=RUN_1),
        prior=m3,
        kind="restore",
    )
    return [m1, m2, m3, m4]


class TestChainStructure:
    def test_shuffled_input__deterministic_order(self, tmp_path: Path) -> None:
        m1, m2, m3, m4 = _worked_example(tmp_path)
        chain = read_manifest_chain([m3, m1, m4, m2])
        assert [s.header.run_id for s in chain.sets] == [RUN_1, RUN_2, RUN_3, RUN_4]
        assert chain.sets[0].sha256 == manifest_sha256(m1)

    def test_empty_input__empty_chain(self) -> None:
        chain = read_manifest_chain([])
        assert chain.sets == ()

    def test_forked_chain__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        fork_a = _apply_set(tmp_path / "fa.jsonl", RUN_2, *_pair(RUN_2, 2, base_seq=1), prior=m1)
        fork_b = _apply_set(tmp_path / "fb.jsonl", RUN_3, *_pair(RUN_3, 3, base_seq=1), prior=m1)
        with pytest.raises(ArtifactError, match="fork"):
            read_manifest_chain([m1, fork_a, fork_b])

    def test_gap__rejected(self, tmp_path: Path) -> None:
        m1, m2, m3, _m4 = _worked_example(tmp_path)
        del m2
        with pytest.raises(ArtifactError, match=r"root|link"):
            read_manifest_chain([m1, m3])  # m3's prior (m2) not supplied

    def test_wrong_prior_hash__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 2, base_seq=1), prior=m1)
        lines = m2.read_text().splitlines()
        header = json.loads(lines[0])
        header["prior_manifest_sha256"] = SHA_C
        header["prior_attempt"]["manifest_sha256"] = SHA_C
        m2.write_text("\n".join([json.dumps(header), *lines[1:]]) + "\n")
        with pytest.raises(ArtifactError, match=r"root|link"):
            read_manifest_chain([m1, m2])

    def test_mixed_plan__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(
            tmp_path / "m2.jsonl",
            RUN_2,
            *_pair(RUN_2, 2, base_seq=1),
            prior=m1,
            plan_sha256="sha256:" + "d" * 64,
        )
        with pytest.raises(ArtifactError, match="plan"):
            read_manifest_chain([m1, m2])

    def test_duplicate_run_id__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_1, *_pair(RUN_1, 2, base_seq=1), prior=m1)
        with pytest.raises(ArtifactError, match="run"):
            read_manifest_chain([m1, m2])

    def test_apply_after_restore__rejected(self, tmp_path: Path) -> None:
        m1, m2, m3, _m4 = _worked_example(tmp_path)
        late_apply = _apply_set(
            tmp_path / "late.jsonl", RUN_4, *_pair(RUN_4, 9, base_seq=1), prior=m3
        )
        with pytest.raises(ArtifactError, match=r"apply|restore"):
            read_manifest_chain([m1, m2, m3, late_apply])


class TestChainLifecycle:
    def test_worked_example__accepted(self, tmp_path: Path) -> None:
        chain = read_manifest_chain(_worked_example(tmp_path))
        assert len(chain.sets) == 4

    def test_restore_undoing_unknown_action__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        ghost = _inverse(RUN_3, f"{PLAN_RUN}/a99", 1, seq=1, result="intent", undoes_run=RUN_1)
        m3 = _apply_set(tmp_path / "m3.jsonl", RUN_3, ghost, prior=m1, kind="restore")
        with pytest.raises(ArtifactError, match="undoes"):
            read_manifest_chain([m1, m3])

    def test_contradictory_terminal_after_applied__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        redo_intent = _record(RUN_2, 1, seq=1, result="intent")
        redo_failed = _record(RUN_2, 1, seq=2, result="failed")
        redo_failed["after_sha256"] = None
        redo_failed["error"] = {"class": "ERR-003", "message": "late failure"}
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, redo_intent, redo_failed, prior=m1)
        with pytest.raises(ArtifactError, match=r"applied|contradict"):
            read_manifest_chain([m1, m2])

    def test_failed_then_retry_to_applied__legal(self, tmp_path: Path) -> None:
        failed_intent = _record(RUN_1, 1, seq=1, result="intent")
        failed_terminal = _record(RUN_1, 1, seq=2, result="failed")
        failed_terminal["after_sha256"] = None
        failed_terminal["error"] = {"class": "ERR-003", "message": "boom"}
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, failed_intent, failed_terminal)
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 1, base_seq=1), prior=m1)
        states = reduce_lifecycle(read_manifest_chain([m1, m2]))
        assert states[A1].state == "applied"

    def test_standalone_terminal_closing_dangling_intent__accepted(self, tmp_path: Path) -> None:
        """CR-NEW-002: an adjudication terminal in a later set is legal when it
        closes exactly one earlier dangling intent with immutable agreement."""
        intent = _record(RUN_1, 1, seq=1, result="intent")
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, intent)
        closure = _record(RUN_2, 1, seq=1, result="applied")
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, closure, prior=m1)
        chain = read_manifest_chain([m1, m2])
        assert reduce_lifecycle(chain)[A1].state == "applied"

    def test_standalone_terminal_closing_nothing__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        orphan = _record(RUN_2, 7, seq=1, result="applied")
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, orphan, prior=m1)
        with pytest.raises(ArtifactError, match="clos"):
            read_manifest_chain([m1, m2])

    def test_single_set_chain_with_standalone_terminal__rejected(self, tmp_path: Path) -> None:
        orphan = _record(RUN_1, 1, seq=1, result="applied")
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, orphan)
        with pytest.raises(ArtifactError, match="clos"):
            read_manifest_chain([m1])

    def test_standalone_failed_closing_nothing__pre_mutation_shape_accepted(
        self, tmp_path: Path
    ) -> None:
        """Plan C review round 2 (CR-NEW-002): the producer records `failed`
        with NO intent when a stat/staging/backup failure aborts an action
        before any corpus name is touched (the adr-0019 pre-mutation shape) —
        it asserts a no-op and closes nothing. The closure rule rejecting it
        made every manifest containing an ordinary pre-mutation failure
        unresumable and unrestorable; only ADOPTION terminals (`applied`)
        assert a mutation and must close a dangling intent."""
        failed = _record(RUN_1, 1, seq=1, result="failed", after_sha256=None)
        failed["error"] = {"class": "ERR-004", "message": "backup failed"}
        failed["source_identity"] = None
        failed["expected_published_identity"] = None
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, failed)
        chain = read_manifest_chain([m1])
        assert reduce_lifecycle(chain)[A1].state == "failed"

    def test_standalone_failed_then_retry_to_applied__legal(self, tmp_path: Path) -> None:
        """The pre-mutation failure exists to be RETRIED: failed -> intent ->
        applied across sets is the recovery path the shape is for."""
        failed = _record(RUN_1, 1, seq=1, result="failed", after_sha256=None)
        failed["error"] = {"class": "ERR-004", "message": "backup failed"}
        failed["source_identity"] = None
        failed["expected_published_identity"] = None
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, failed)
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 1, base_seq=1), prior=m1)
        states = reduce_lifecycle(read_manifest_chain([m1, m2]))
        assert states[A1].state == "applied"

    def test_closure_with_diverging_immutables__rejected(self, tmp_path: Path) -> None:
        intent = _record(RUN_1, 1, seq=1, result="intent")
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, intent)
        closure = _record(RUN_2, 1, seq=1, result="applied", before_sha256=SHA_C)
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, closure, prior=m1)
        with pytest.raises(ArtifactError, match=r"immutable|clos"):
            read_manifest_chain([m1, m2])


class TestChainEdges:
    def test_two_roots__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 2, base_seq=1))
        with pytest.raises(ArtifactError, match="exactly one root"):
            read_manifest_chain([m1, m2])

    def test_mixed_source_root__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        other_root = [
            r
            | {
                "run_id": RUN_2,
                "original_path": f"/other/f{i}.md",
                "target_path": f"/other/f{i}.md",
            }
            for i, r in enumerate(_pair(RUN_2, 2, base_seq=1), start=2)
        ]
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, *other_root, prior=m1, source_root="/other")
        with pytest.raises(ArtifactError, match="source_root"):
            read_manifest_chain([m1, m2])

    def test_report_edge_naming_a_chain_run__rejected(self, tmp_path: Path) -> None:
        """A report-flavored edge names a run that DID produce a manifest in
        this chain — the attempt chain and subchain would disagree."""
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(
            tmp_path / "m2.jsonl",
            RUN_2,
            *_pair(RUN_2, 2, base_seq=1),
            prior=m1,
            prior_attempt={"run_id": RUN_1, "report_sha256": SHA_C, "manifest_sha256": None},
        )
        with pytest.raises(ArtifactError, match=r"report-only|report-flavored"):
            read_manifest_chain([m1, m2])

    def test_failed_closure_terminal__accepted_with_null_after(self, tmp_path: Path) -> None:
        """The cross-set failed-after exemption: a FAILED adjudication terminal
        nulls after_sha256 while the intent carried the expected hash."""
        intent = _record(RUN_1, 1, seq=1, result="intent")
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, intent)
        closure = _record(RUN_2, 1, seq=1, result="failed", after_sha256=None)
        closure["error"] = {"class": "ERR-003", "message": "adjudicated failed"}
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, closure, prior=m1)
        states = reduce_lifecycle(read_manifest_chain([m1, m2]))
        assert states[A1].state == "failed"


class TestAttemptLineage:
    def test_root_with_report_flavored_edge__accepted(self, tmp_path: Path) -> None:
        """CR-004: the R1-report-only → R2-first-manifest shape — a root
        manifest (null prior link) whose predecessor was report-only."""
        edge: dict[str, object] = {"run_id": RUN_1, "report_sha256": SHA_C, "manifest_sha256": None}
        m2 = _apply_set(
            tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 1, base_seq=1), prior_attempt=edge
        )
        chain = read_manifest_chain([m2])
        assert chain.sets[0].header.prior_attempt is not None

    def test_root_with_manifest_flavored_edge__rejected(self, tmp_path: Path) -> None:
        edge: dict[str, object] = {"run_id": RUN_1, "report_sha256": None, "manifest_sha256": SHA_C}
        m2 = _apply_set(
            tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 1, base_seq=1), prior_attempt=edge
        )
        with pytest.raises(ArtifactError, match=r"attempt|prior"):
            read_manifest_chain([m2])

    def test_manifest_edge_disagreeing_with_subchain__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(
            tmp_path / "m2.jsonl",
            RUN_2,
            *_pair(RUN_2, 2, base_seq=1),
            prior=m1,
            prior_attempt={"run_id": RUN_1, "report_sha256": None, "manifest_sha256": SHA_C},
        )
        with pytest.raises(ArtifactError, match="attempt"):
            read_manifest_chain([m1, m2])

    def test_non_root_without_edge__rejected(self, tmp_path: Path) -> None:
        m1 = _apply_set(tmp_path / "m1.jsonl", RUN_1, *_pair(RUN_1, 1, base_seq=1))
        m2 = _apply_set(tmp_path / "m2.jsonl", RUN_2, *_pair(RUN_2, 2, base_seq=1), prior=m1)
        lines = m2.read_text().splitlines()
        header = json.loads(lines[0])
        header["prior_attempt"] = None
        m2.write_text("\n".join([json.dumps(header), *lines[1:]]) + "\n")
        with pytest.raises(ArtifactError, match="attempt"):
            read_manifest_chain([m1, m2])


class TestReduceLifecycle:
    def test_worked_example__all_restored(self, tmp_path: Path) -> None:
        chain = read_manifest_chain(_worked_example(tmp_path))
        states = reduce_lifecycle(chain)
        assert {k: v.state for k, v in states.items()} == {
            A1: "restored",
            A2: "restored",
            A3: "restored",
        }

    def test_truncated_to_m1__applied_and_pending_intent(self, tmp_path: Path) -> None:
        m1, *_ = _worked_example(tmp_path)
        states = reduce_lifecycle(read_manifest_chain([m1]))
        assert states[A1].state == "applied"
        assert states[A2].state == "pending-intent"

    def test_through_m3__a2_pending_restore(self, tmp_path: Path) -> None:
        m1, m2, m3, _m4 = _worked_example(tmp_path)
        states = reduce_lifecycle(read_manifest_chain([m1, m2, m3]))
        assert states[A3].state == "restored"
        assert states[A2].state == "pending-restore"
        assert states[A1].state == "applied"
