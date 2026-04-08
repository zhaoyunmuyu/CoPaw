# -*- coding: utf-8 -*-
"""Integration tests for tenant model configuration API endpoints."""
# pylint:disable=consider-using-with,redefined-outer-name,too-many-statements
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from unittest.mock import patch

import httpx
import pytest

from swe.tenant_models.manager import TenantModelManager
from swe.tenant_models.models import (
    ModelSlot,
    RoutingConfig,
    TenantModelConfig,
    TenantProviderConfig,
)


def _find_free_port(host: str = "127.0.0.1") -> int:
    """Bind to port 0 and return the OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.listen(1)
        return sock.getsockname()[1]


def _tee_stream(stream, buffer: list[str]) -> None:
    """Read subprocess output, print it live, and keep a copy."""
    try:
        for line in iter(stream.readline, ""):
            buffer.append(line)
            print(line, end="", flush=True)
    finally:
        stream.close()


@pytest.fixture
def tenant1_config():
    """Create a sample configuration for tenant1."""
    return TenantModelConfig(
        version="1.0",
        providers=[
            TenantProviderConfig(
                id="tenant1-openai",
                type="openai",
                api_key="tenant1-key",
                models=["gpt-4"],
                enabled=True,
            ),
        ],
        routing=RoutingConfig(
            mode="cloud_first",
            slots={
                "cloud": ModelSlot(
                    provider_id="tenant1-openai",
                    model="gpt-4",
                ),
                "local": ModelSlot(
                    provider_id="tenant1-ollama",
                    model="llama2",
                ),
            },
        ),
    )


@pytest.fixture
def tenant2_config():
    """Create a sample configuration for tenant2."""
    return TenantModelConfig(
        version="1.0",
        providers=[
            TenantProviderConfig(
                id="tenant2-anthropic",
                type="anthropic",
                api_key="tenant2-key",
                models=["claude-3"],
                enabled=True,
            ),
        ],
        routing=RoutingConfig(
            mode="local_first",
            slots={
                "local": ModelSlot(
                    provider_id="tenant2-ollama",
                    model="mistral",
                ),
                "cloud": ModelSlot(
                    provider_id="tenant2-anthropic",
                    model="claude-3",
                ),
            },
        ),
    )


def test_tenant_model_api_returns_tenant_specific_config(
    tmp_path,
    tenant1_config,
) -> None:
    """Test that the API returns tenant-specific configuration."""
    # Setup tenant configuration
    with patch("swe.tenant_models.manager.SECRET_DIR", tmp_path):
        # Clear cache before test
        TenantModelManager.invalidate_cache()

        # Save tenant1 configuration
        TenantModelManager.save("tenant1", tenant1_config)

        # Start the app
        host = "127.0.0.1"
        port = _find_free_port(host)
        log_lines: list[str] = []

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "swe",
                "app",
                "--host",
                host,
                "--port",
                str(port),
                "--log-level",
                "info",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None

        log_thread = threading.Thread(
            target=_tee_stream,
            args=(process.stdout, log_lines),
            daemon=True,
        )
        log_thread.start()

        try:
            max_wait = 60
            start_time = time.time()
            backend_ready = False

            with httpx.Client(timeout=5.0, trust_env=False) as client:
                # Wait for backend to be ready
                while time.time() - start_time < max_wait:
                    if process.poll() is not None:
                        logs = "".join(log_lines)[-4000:]
                        raise AssertionError(
                            f"Process exited early with code {process.returncode}.\n"
                            f"Logs:\n{logs}",
                        )

                    try:
                        response = client.get(
                            f"http://{host}:{port}/api/version",
                        )
                        if response.status_code == 200:
                            backend_ready = True
                            break
                    except (httpx.ConnectError, httpx.TimeoutException):
                        time.sleep(1.0)

                if not backend_ready:
                    logs = "".join(log_lines)[-4000:]
                    raise AssertionError(
                        "Backend did not start within timeout period.\n"
                        f"Logs:\n{logs}",
                    )

                # Test the tenant providers API endpoint
                # Note: We need to set tenant context via header or middleware
                # For this test, we'll use a custom header that the middleware recognizes
                response = client.get(
                    f"http://{host}:{port}/api/providers",
                    headers={"X-Tenant-Id": "tenant1"},
                )

                # The API should return tenant1's configuration
                assert response.status_code == 200
                data = response.json()

                # Verify response structure
                assert "tenant_id" in data
                assert "providers" in data
                assert "routing" in data
                assert "active_mode" in data
                assert "active_slot" in data

                # Verify tenant1's specific data
                assert data["tenant_id"] == "tenant1"
                assert len(data["providers"]) == 1
                assert data["providers"][0]["id"] == "tenant1-openai"
                assert data["providers"][0]["api_key"] == "tenant1-key"
                assert data["active_mode"] == "cloud_first"
                assert data["active_slot"]["provider_id"] == "tenant1-openai"
                assert data["active_slot"]["model"] == "gpt-4"

        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

            log_thread.join(timeout=2)
            # Clear cache after test
            TenantModelManager.invalidate_cache()


def test_tenant_isolation_different_tenants_return_different_configs(
    tmp_path,
    tenant1_config,
    tenant2_config,
) -> None:
    """Test that different tenants receive different configurations."""
    # Setup tenant configurations
    with patch("swe.tenant_models.manager.SECRET_DIR", tmp_path):
        # Clear cache before test
        TenantModelManager.invalidate_cache()

        # Save both tenant configurations
        TenantModelManager.save("tenant1", tenant1_config)
        TenantModelManager.save("tenant2", tenant2_config)

        # Start the app
        host = "127.0.0.1"
        port = _find_free_port(host)
        log_lines: list[str] = []

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "swe",
                "app",
                "--host",
                host,
                "--port",
                str(port),
                "--log-level",
                "info",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None

        log_thread = threading.Thread(
            target=_tee_stream,
            args=(process.stdout, log_lines),
            daemon=True,
        )
        log_thread.start()

        try:
            max_wait = 60
            start_time = time.time()
            backend_ready = False

            with httpx.Client(timeout=5.0, trust_env=False) as client:
                # Wait for backend to be ready
                while time.time() - start_time < max_wait:
                    if process.poll() is not None:
                        logs = "".join(log_lines)[-4000:]
                        raise AssertionError(
                            f"Process exited early with code {process.returncode}.\n"
                            f"Logs:\n{logs}",
                        )

                    try:
                        response = client.get(
                            f"http://{host}:{port}/api/version",
                        )
                        if response.status_code == 200:
                            backend_ready = True
                            break
                    except (httpx.ConnectError, httpx.TimeoutException):
                        time.sleep(1.0)

                if not backend_ready:
                    logs = "".join(log_lines)[-4000:]
                    raise AssertionError(
                        "Backend did not start within timeout period.\n"
                        f"Logs:\n{logs}",
                    )

                # Request configuration for tenant1
                response1 = client.get(
                    f"http://{host}:{port}/api/providers",
                    headers={"X-Tenant-Id": "tenant1"},
                )
                assert response1.status_code == 200
                data1 = response1.json()

                # Request configuration for tenant2
                response2 = client.get(
                    f"http://{host}:{port}/api/providers",
                    headers={"X-Tenant-Id": "tenant2"},
                )
                assert response2.status_code == 200
                data2 = response2.json()

                # Verify tenant isolation - configurations should be different
                assert data1["tenant_id"] == "tenant1"
                assert data2["tenant_id"] == "tenant2"

                # Verify different providers
                assert data1["providers"][0]["id"] == "tenant1-openai"
                assert data1["providers"][0]["type"] == "openai"
                assert data2["providers"][0]["id"] == "tenant2-anthropic"
                assert data2["providers"][0]["type"] == "anthropic"

                # Verify different routing modes
                assert data1["active_mode"] == "cloud_first"
                assert data2["active_mode"] == "local_first"

                # Verify different active slots
                assert data1["active_slot"]["provider_id"] == "tenant1-openai"
                assert data1["active_slot"]["model"] == "gpt-4"
                assert data2["active_slot"]["provider_id"] == "tenant2-ollama"
                assert data2["active_slot"]["model"] == "mistral"

                # Ensure the configurations are truly different
                assert data1 != data2

        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

            log_thread.join(timeout=2)
            # Clear cache after test
            TenantModelManager.invalidate_cache()
