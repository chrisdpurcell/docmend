"""CR-001 regression: the shared wire types must be importable from every
consumer module in a clean process — the Plan B review found two would-be
cycles (manifest→atomic and manifest→artifacts→report) had ObjectIdentity or
PriorAttempt been owned by writer.manifest.
"""

import subprocess
import sys


def test_wire_type_consumers__import_in_clean_process() -> None:
    code = (
        "import docmend.lineage, docmend.report, docmend.artifacts, "
        "docmend.writer.atomic, docmend.writer.manifest"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
