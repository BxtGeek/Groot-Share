"""Configuration persistence using JSON with restrictive permissions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from groot_share.app.settings import CONFIG_PATH


class ConfigError(Exception):
    pass


def load_config() -> dict[str, Any]:
    path = CONFIG_PATH
    if not path.exists():
        return {"storages": {}, "version": 1}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ConfigError("Invalid config format: expected JSON object.")
        return data
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file: {exc}")


def save_config(data: dict[str, Any]) -> None:
    path = CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write via temp file in same directory
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".storages_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        # Restrictive permissions (owner read/write only)
        os.chmod(tmp, 0o600)
        # Atomic rename
        os.rename(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def list_storages() -> dict[str, dict[str, Any]]:
    config = load_config()
    return config.get("storages", {})


def get_storage(storage_id: str) -> dict[str, Any] | None:
    return list_storages().get(storage_id)


def add_storage(storage_id: str, config: dict[str, Any]) -> dict[str, Any]:
    data = load_config()
    data.setdefault("storages", {})[storage_id] = config
    save_config(data)
    return config


def update_storage(storage_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    data = load_config()
    existing = data.get("storages", {}).get(storage_id)
    if existing is None:
        raise ConfigError(f"Storage not found: {storage_id}")
    # Merge updates, never expose secrets in responses — handled by endpoints
    existing.update(updates)
    save_config(data)
    return existing


def delete_storage(storage_id: str) -> None:
    data = load_config()
    storages = data.get("storages", {})
    if storage_id in storages:
        del storages[storage_id]
    save_config(data)


def get_storage_config_path() -> Path:
    return CONFIG_PATH