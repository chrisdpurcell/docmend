"""Shared test configuration.

Registers the Hypothesis CI settings profile (OQ-019): CI runners are slower
and noisier than dev machines, so the deadline is disabled there rather than
letting flaky per-example timing fail the gate. Locally the default profile
(with its deadline) stays in force, which keeps genuinely slow code visible
during development.
"""

import os

from hypothesis import settings

settings.register_profile("ci", deadline=None)
if os.environ.get("CI"):
    settings.load_profile("ci")
