# -*- coding: utf-8 -*-
"""Regression tests for CronManager lazy imports."""

import subprocess
import sys


def test_importing_cron_manager_does_not_import_heavy_runtime_modules():
    """CronManager import should avoid heavy config and memory runtime imports."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import swe.app.crons.manager; "
                "raise SystemExit("
                "0 if 'swe.config.config' not in sys.modules "
                "and 'swe.config.utils' not in sys.modules "
                "and not any("
                "name.startswith('agentscope.memory') "
                "for name in sys.modules"
                ") else 1)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
