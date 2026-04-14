# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_import_swe_loads_dev_defaults_before_constant(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    env["SWE_ENV"] = "dev"
    env["SWE_WORKING_DIR"] = str(tmp_path / ".swe")
    env["SWE_SECRET_DIR"] = str(tmp_path / ".swe.secret")
    env.pop("SWE_OPENAPI_DOCS", None)
    env.pop("SWE_LOG_LEVEL", None)

    script = """
import json
import os
import swe
import swe.constant as constant

print(json.dumps({
    "env_docs": os.environ.get("SWE_OPENAPI_DOCS"),
    "env_log_level": os.environ.get("SWE_LOG_LEVEL"),
    "docs_enabled": constant.DOCS_ENABLED,
}))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root,
    )

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload == {
        "env_docs": "true",
        "env_log_level": "debug",
        "docs_enabled": True,
    }
