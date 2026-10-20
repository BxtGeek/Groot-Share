"""Builds storage adapters from configuration and exposes a registry."""

from __future__ import annotations

from typing import Any

from groot_share.app.storage import (
    LocalStorageAdapter,
    MountedNFSStorageAdapter,
    MountedSMBStorageAdapter,
    StorageAdapter,
    StorageError,
)


def build_adapter(storage_id: str, config: dict[str, Any]) -> StorageAdapter:
    storage_type = (config.get("storage_type") or "local").lower()
    if storage_type == "local":
        return LocalStorageAdapter(storage_id, config)
    if storage_type == "smb":
        return MountedSMBStorageAdapter(storage_id, config)
    if storage_type == "nfs":
        return MountedNFSStorageAdapter(storage_id, config)
    raise StorageError(f"Unknown storage type: {storage_type}")


def list_adapters() -> dict[str, StorageAdapter]:
    from groot_share.app.config import list_storages

    adapters: dict[str, StorageAdapter] = {}
    for storage_id, config in list_storages().items():
        if not config.get("enabled", True):
            continue
        try:
            adapters[storage_id] = build_adapter(storage_id, config)
        except StorageError:
            continue
    return adapters


def get_adapter(storage_id: str) -> StorageAdapter:
    from groot_share.app.config import get_storage

    config = get_storage(storage_id)
    if config is None:
        raise StorageError(f"Storage not found: {storage_id}")
    if not config.get("enabled", True):
        raise StorageError(f"Storage is disabled: {storage_id}")
    return build_adapter(storage_id, config)