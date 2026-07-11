"""Shared recovery-lineage wire primitives (adr-0019).

Dependency-neutral BY CONTRACT (Plan B review CR-001): this module may import
only stdlib, pydantic, and docmend.inventory's aliases — writer/atomic.py,
writer/manifest.py, and report.py all consume it, and any heavier import here
re-creates the cycles the review found (manifest→atomic and
manifest→artifacts→report both already exist in the import graph).
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from docmend.inventory import RunId, Sha256


class ObjectIdentity(BaseModel):
    """Exact (st_dev, st_ino) pair — the adjudication predicates' currency
    (safety-core design F4 rounds 3-4). Device mismatch refuses as
    external-interference, never substitutes a current device number."""

    model_config = ConfigDict(extra="forbid", strict=True)

    dev: Annotated[int, Field(ge=0)]
    ino: Annotated[int, Field(ge=0)]


class PriorAttempt(BaseModel):
    """Discriminated attempt-lineage edge (design F6 rounds 4-5): the
    predecessor's run_id plus EITHER its report sha256 OR — when that report
    was never published (the crash-after-manifest-close window) — its
    closed-manifest sha256. Persisted redundantly in the apply manifest
    header AND the apply report so the edge survives whichever artifact an
    interruption erases."""

    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: RunId
    report_sha256: Sha256 | None
    manifest_sha256: Sha256 | None

    @model_validator(mode="after")
    def _exactly_one_sha(self) -> Self:
        if (self.report_sha256 is None) == (self.manifest_sha256 is None):
            msg = "prior_attempt carries exactly one of report_sha256 or manifest_sha256"
            raise ValueError(msg)
        return self
