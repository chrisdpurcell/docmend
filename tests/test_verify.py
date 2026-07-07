"""verify engine unit tests (FR-014, adr-0012) — the parts the CLI journey in
tests/test_cli_verify.py does not isolate cleanly.
"""

from docmend.report import ErrorInfo
from docmend.verify import reconcile_manifest
from docmend.writer.manifest import ManifestRecord

RUN_ID = "run_20260707T000000Z_0000aa"
SHA_A = "sha256:" + "a" * 64
UUID7 = "01980000-0000-7000-8000-000000000001"


def test_reconcile_skips_failed_records() -> None:
    """A result=='failed' record left the original untouched (spec 10.4), so there
    is no applied output to reconcile — reconcile must not manufacture a finding
    (and must not touch the filesystem for it)."""
    failed = ManifestRecord(
        run_id=RUN_ID,
        action_id=f"{RUN_ID}/a1",
        docmend_id=UUID7,
        seq=1,
        recorded_at="2026-07-07T00:00:00+00:00",
        operation="rewrite",
        original_path="/nonexistent/a.txt",
        target_path="/nonexistent/a.txt",
        backup_path=None,
        before_sha256=SHA_A,
        after_sha256=None,
        result="failed",
        error=ErrorInfo(error_class="ERR-003", message="boom"),
    )

    assert reconcile_manifest([failed]) == []
