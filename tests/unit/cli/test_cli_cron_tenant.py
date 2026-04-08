# -*- coding: utf-8 -*-
"""Cron CLI tenant header regression tests."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from swe.cli.cron_cmd import cron_group


class _Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True}


def test_cron_create_passes_tenant_header():
    runner = CliRunner()

    with patch("swe.cli.cron_cmd.client") as mock_client:
        mock_http = MagicMock()
        mock_http.__enter__.return_value = mock_http
        mock_http.post.return_value = _Response()
        mock_client.return_value = mock_http

        result = runner.invoke(
            cron_group,
            [
                "create",
                "--type",
                "agent",
                "--name",
                "tenant cron",
                "--cron",
                "* * * * *",
                "--channel",
                "console",
                "--target-user",
                "user-a",
                "--target-session",
                "session-a",
                "--text",
                "ping",
                "--timezone",
                "UTC",
                "--tenant-id",
                "tenant-a",
            ],
        )

    assert result.exit_code == 0
    _, kwargs = mock_http.post.call_args
    assert kwargs["headers"]["X-Tenant-Id"] == "tenant-a"
