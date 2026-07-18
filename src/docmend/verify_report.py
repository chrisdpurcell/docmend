"""Durable verification evidence (FR-014, adr-0005).

The checked-in verify-report schema is the external contract. These strict
models conform to it; artifacts.py validates and reconciles every write.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from docmend.inventory import RunId, Sha256

VERIFY_REPORT_SCHEMA_VERSION = "1.0"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class VerificationInput(_StrictModel):
    kind: Literal["plan", "report", "manifest"]
    path: Annotated[str, Field(min_length=1)]
    run_id: RunId
    sha256: Sha256


class VerifyFindingRecord(_StrictModel):
    path: Annotated[str, Field(min_length=1)]
    check: Annotated[str, Field(min_length=1)]
    detail: Annotated[str, Field(min_length=1)]


class VerifyReport(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_kind: Literal["docmend/verify-report"] = Field(
        default="docmend/verify-report", alias="schema"
    )
    schema_version: Literal["1.0"] = VERIFY_REPORT_SCHEMA_VERSION
    run_id: RunId
    generated_by: Annotated[str, Field(min_length=1)]
    verified_path: Annotated[str, Field(min_length=1)]
    source_root: Annotated[str, Field(min_length=1)]
    started_at: str
    completed_at: str
    inputs: list[VerificationInput]
    checked_files: Annotated[int, Field(ge=0)]
    findings: list[VerifyFindingRecord]
    clean: bool
