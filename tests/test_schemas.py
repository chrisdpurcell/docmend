"""Artifact schema contract tests — adr-0005 (spec: DR-001, IR-007; OQ-004).

Three layers of protection for the hand-authored schemas:

1. Every checked-in schema is itself valid Draft 2020-12 and strict
   (additionalProperties:false on every object) — a schema that drifted loose
   would silently accept malformed artifacts.
2. Every schema is SATISFIABLE: a minimal valid instance exists for each,
   including the plan/report/manifest contracts that MS-2/MS-3 will implement.
   Metaschema validity alone would pass a schema that rejects everything.
3. The internal pydantic Inventory model stays compatible with the external
   contract: identical property-name sets, and the model never requires a field
   the contract does not (adr-0005: models conform to the schemas, never the
   reverse).
"""

import uuid
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from docmend.artifacts import (
    ARTIFACT_KINDS,
    ArtifactError,
    ArtifactKind,
    load_schema,
    validate_artifact,
)
from docmend.config import DocmendConfig
from docmend.inventory import Inventory

RUN_ID = "run_20260706T000000Z_abc123"
ACTION_ID = f"{RUN_ID}/a1"
SHA = "sha256:" + "0" * 64
TIMESTAMP = "2026-07-06T00:00:00Z"


def _check_schema(schema: dict[str, object]) -> None:
    checker = cast("Any", Draft202012Validator)
    checker.check_schema(schema)


class TestSchemaFiles:
    @pytest.mark.parametrize("kind", ARTIFACT_KINDS)
    def test_schema__is_valid_draft_2020_12(self, kind: ArtifactKind) -> None:
        _check_schema(load_schema(kind))

    @pytest.mark.parametrize("kind", ARTIFACT_KINDS)
    def test_schema__every_object_is_strict(self, kind: ArtifactKind) -> None:
        """adr-0005: strict additionalProperties:false everywhere, no drift."""
        offenders: list[str] = []

        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                typed = cast("dict[str, object]", node)
                if typed.get("type") == "object" and typed.get("additionalProperties") is not False:
                    offenders.append(path or "(root)")
                for key, value in typed.items():
                    walk(value, f"{path}/{key}")
            elif isinstance(node, list):
                for i, value in enumerate(cast("list[object]", node)):
                    walk(value, f"{path}[{i}]")

        walk(load_schema(kind), "")
        assert not offenders, f"non-strict object schemas in {kind}: {offenders}"

    @pytest.mark.parametrize("kind", ARTIFACT_KINDS)
    def test_schema__declares_kind_and_version_fields(self, kind: ArtifactKind) -> None:
        schema = load_schema(kind)
        properties = cast("dict[str, dict[str, object]]", schema["properties"])
        assert str(properties["schema"]["const"]).startswith("docmend/")
        assert "pattern" in properties["schema_version"]
        required = cast("list[str]", schema["required"])
        assert {"schema", "schema_version", "run_id"} <= set(required)


def _minimal_plan() -> dict[str, object]:
    return {
        "schema": "docmend/plan",
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "generated_at": TIMESTAMP,
        "generated_by": "docmend 0.1.0",
        "inventory_ref": {"path": "inv.json", "run_id": RUN_ID, "sha256": SHA},
        # The live default config dump must satisfy the plan's config_snapshot —
        # this doubles as the drift guard between config.py and plan.schema.json.
        "config": DocmendConfig().model_dump(mode="json"),
        "actions": [
            {
                "action_id": ACTION_ID,
                "docmend_id": str(uuid.uuid7()),
                "path": "a.txt",
                "source_sha256": SHA,
                "source_size_bytes": 12,
                "operations": ["reencode", "normalize_newlines", "rename"],
                "target_path": "a.md",
                "provenance": {
                    "detected_encoding": {
                        "name": "utf-8",
                        "confidence": 1.0,
                        "method": "utf8-strict",
                    },
                    "newline_style": "crlf",
                },
            }
        ],
        "skips": [{"path": "b.dat", "reason": "nul-bytes", "detail": None}],
        "totals": {"actions": 1, "skips": 1},
    }


def _minimal_report() -> dict[str, object]:
    return {
        "schema": "docmend/report",
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "generated_by": "docmend 0.1.0",
        "plan_ref": {"path": "plan.json", "run_id": RUN_ID, "sha256": SHA},
        "dry_run": True,
        "started_at": TIMESTAMP,
        "completed_at": TIMESTAMP,
        "outcomes": [
            {
                "action_id": ACTION_ID,
                "path": "a.txt",
                "status": "would_apply",
                "before_sha256": SHA,
                "after_sha256": None,
                "skip_reason": None,
                "error": None,
            }
        ],
        "totals": {"applied": 0, "would_apply": 1, "skipped": 0, "failed": 0},
    }


def _minimal_manifest_record() -> dict[str, object]:
    return {
        "schema": "docmend/manifest-record",
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "action_id": ACTION_ID,
        "docmend_id": str(uuid.uuid7()),
        "seq": 1,
        "recorded_at": TIMESTAMP,
        "operation": "rename_and_rewrite",
        "original_path": "/library/a.txt",
        "target_path": "/library/a.md",
        "backup_path": None,
        "before_sha256": SHA,
        "after_sha256": SHA,
        "result": "applied",
        "error": None,
    }


class TestSchemaSatisfiability:
    """A minimal valid instance exists for every contract (incl. MS-2/MS-3 ones)."""

    def test_plan_schema__accepts_minimal_instance_and_default_config(self) -> None:
        validate_artifact("plan", _minimal_plan())

    def test_report_schema__accepts_minimal_instance(self) -> None:
        validate_artifact("report", _minimal_report())

    def test_manifest_schema__accepts_minimal_record(self) -> None:
        validate_artifact("manifest", _minimal_manifest_record())

    def test_manifest_schema__rejects_missing_identity_field(self) -> None:
        record = _minimal_manifest_record()
        del record["docmend_id"]
        with pytest.raises(ArtifactError, match="docmend_id"):
            validate_artifact("manifest", record)


def _resolve(node: dict[str, object], root: dict[str, object]) -> dict[str, object]:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        target: dict[str, object] = root
        for part in ref[2:].split("/"):
            target = cast("dict[str, object]", target[part])
        return _resolve(target, root)
    return node


def _object_shapes(
    node: dict[str, object],
    root: dict[str, object],
    path: str,
    out: dict[str, tuple[set[str], set[str]]],
) -> None:
    """Collect {property-path: (property names, required names)} for every object."""
    node = _resolve(node, root)
    branches: list[object] = [node]
    for union_key in ("oneOf", "anyOf"):
        if union_key in node:
            branches = cast("list[object]", node[union_key])
    for branch_obj in branches:
        branch = _resolve(cast("dict[str, object]", branch_obj), root)
        properties = branch.get("properties")
        if isinstance(properties, dict):
            typed_props = cast("dict[str, dict[str, object]]", properties)
            required = cast("list[str]", branch.get("required", []))
            out[path] = (set(typed_props), set(required))
            for name, sub in typed_props.items():
                _object_shapes(sub, root, f"{path}.{name}" if path else name, out)
        items = branch.get("items")
        if isinstance(items, dict):
            _object_shapes(cast("dict[str, object]", items), root, f"{path}[]", out)


class TestPydanticCrossCheck:
    """spec: DR-001 — the internal model and external contract cannot drift apart."""

    def test_inventory_model__matches_hand_authored_schema(self) -> None:
        hand: dict[str, tuple[set[str], set[str]]] = {}
        _object_shapes(load_schema("inventory"), load_schema("inventory"), "", hand)

        emitted = cast("dict[str, object]", Inventory.model_json_schema(by_alias=True))
        model: dict[str, tuple[set[str], set[str]]] = {}
        _object_shapes(emitted, emitted, "", model)

        assert set(hand) == set(model), "object paths differ between schema and model"
        for path, (hand_props, hand_required) in hand.items():
            model_props, model_required = model[path]
            assert hand_props == model_props, f"property names differ at {path!r}"
            # The model may require less (fields with defaults are always emitted
            # anyway) but must never require MORE than the durable contract.
            assert model_required <= hand_required, f"model over-requires at {path!r}"
