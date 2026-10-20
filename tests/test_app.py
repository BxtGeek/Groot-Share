"""Tests for Groot Share."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from groot_share.app.main import create_app
from groot_share.app.settings import ADMIN_PASSWORD
from groot_share.app.config import load_config, save_config


@pytest.fixture
def client():
    # Use a temporary config directory
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CONFIG_PATH"] = str(Path(tmpdir) / "storages.json")
        os.environ["ADMIN_PASSWORD"] = "testpass"
        os.environ["SESSION_SECRET"] = "testsecret"
        os.environ["PERMITTED_ROOTS"] = tmpdir
        # Initialize empty config
        save_config({"storages": {}, "version": 1})
        app = create_app()
        yield TestClient(app)
        # Cleanup is handled by tmpdir


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_redirect(client):
    # Unauthenticated should redirect to login
    resp = client.get("/")
    assert resp.status_code == 302
    assert "login" in resp.headers.get("location", "")


def test_login_success(client):
    resp = client.post("/login", data={"password": "testpass"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("location") == "/"


def test_login_failure(client):
    resp = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert resp.status_code == 400


def test_auth_protected_api(client):
    resp = client.get("/api/storages")
    assert resp.status_code == 401


def test_storages_with_auth(client):
    client.post("/login", data={"password": "testpass"})
    resp = client.get("/api/storages")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_path_traversal_blocked(client):
    client.post("/login", data={"password": "testpass"})
    # Add a storage first
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "storages.json"
        os.environ["CONFIG_PATH"] = str(config_path)
        save_config({
            "storages": {
                "test-local": {
                    "display_name": "Test",
                    "storage_type": "local",
                    "path": tmpdir,
                    "enabled": True,
                    "read_only": False,
                }
            },
            "version": 1,
        })
        resp = client.get("/api/storages/test-local/browse?path=../etc/passwd")
        assert resp.status_code == 400


def test_readonly_storage_prevents_modification(client):
    client.post("/login", data={"password": "testpass"})
    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({
            "storages": {
                "test-ro": {
                    "display_name": "Read Only",
                    "storage_type": "local",
                    "path": tmpdir,
                    "enabled": True,
                    "read_only": True,
                }
            },
            "version": 1,
        })
        resp = client.post("/api/storages/test-ro/upload", data={"path": "", "file": ("test.txt", b"hello")})
        assert resp.status_code == 400
