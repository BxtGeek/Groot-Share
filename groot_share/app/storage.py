"""Storage adapter interface and local implementation."""

from __future__ import annotations

import mimetypes
import os
import posixpath
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from groot_share.app.settings import PERMITTED_ROOTS


class StorageError(RuntimeError):
    """Base exception for storage adapter errors."""

    pass


class PathOutsideRootError(StorageError):
    """Raised when a resolved path escapes the storage root."""

    pass


class StorageNotAvailableError(StorageError):
    """Raised when a storage root directory is missing."""

    pass


class InsufficientPermissionsError(StorageError):
    """Raised when the application cannot read/write the path."""

    pass


class StorageAdapter(ABC):
    """Common interface for all storage adapters."""

    @property
    @abstractmethod
    def storage_id(self) -> str:
        """Unique identifier for this storage configuration."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable storage name."""

    @property
    @abstractmethod
    def storage_type(self) -> str:
        """One of: 'local', 'smb', 'nfs'."""

    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether this storage is enabled."""

    @property
    @abstractmethod
    def is_readonly(self) -> bool:
        """Whether this storage is read-only."""

    @abstractmethod
    def browse(self, relative_path: str = "") -> list[dict[str, Any]]:
        """List directory contents, returning file metadata dicts."""

    @abstractmethod
    def download_file(self, relative_path: str) -> Path:
        """Return Path to file for streaming download."""

    @abstractmethod
    def upload_file(self, relative_path: str, data: bytes | None = None) -> dict[str, Any]:
        """Upload data to a path."""

    @abstractmethod
    def create_dir(self, relative_path: str) -> Path:
        """Create a directory at the given relative path."""

    @abstractmethod
    def rename(self, old_rel: str, new_rel: str) -> Path:
        """Rename from old_rel to new_rel within the same storage root."""

    @abstractmethod
    def delete(self, relative_path: str) -> None:
        """Delete the item at the relative path."""

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """Test that the storage is accessible."""

    def validate_path(self, relative_path: str) -> Path:
        """Validate and resolve a relative path against the storage root."""
        root = self.resolved_root
        if not root.exists():
            raise StorageNotAvailableError(f"Storage root does not exist: {root}")

        # Normalise and resolve
        resolved = (root / relative_path).resolve()

        try:
            resolved.relative_to(root)
        except ValueError:
            raise PathOutsideRootError(
                f"Path escapes storage root: {relative_path} -> {resolved}"
            )

        if not os.access(resolved, os.R_OK):
            raise InsufficientPermissionsError(f"Cannot read path: {resolved}")

        return resolved

    @property
    @abstractmethod
    def resolved_root(self) -> Path:
        """The resolved absolute path of the storage root."""

    @staticmethod
    def safe_filename(filename: str) -> str:
        """Sanitise a filename: strip path separators, null bytes, and traversals."""
        cleaned = filename.strip("/\\")
        if ".." in cleaned.split("/") or ".." in cleaned.split("\\"):
            raise ValueError(f"Unsafe filename containing '..': {filename}")
        if "\x00" in cleaned:
            raise ValueError(f"Unsafe filename containing null byte: {filename}")
        return cleaned or "unnamed"


class LocalStorageAdapter(StorageAdapter):
    """Adapter for local host-mounted directories."""

    def __init__(self, storage_id: str, config: dict[str, Any]):
        self._storage_id = storage_id
        self._config = config
        self._raw_path = config.get("path", "")

    @property
    def storage_id(self) -> str:
        return self._storage_id

    @property
    def display_name(self) -> str:
        return self._config.get("display_name", self._storage_id)

    @property
    def storage_type(self) -> str:
        return "local"

    @property
    def is_enabled(self) -> bool:
        return self._config.get("enabled", True)

    @property
    def is_readonly(self) -> bool:
        return self._config.get("read_only", False)

    @property
    def resolved_root(self) -> Path:
        raw = self._raw_path
        if not raw:
            return Path("/").resolve()
        return Path(raw).resolve()

    def browse(self, relative_path: str = "") -> list[dict[str, Any]]:
        resolved = self.validate_path(relative_path)
        items: list[dict[str, Any]] = []
        try:
            for entry in sorted(resolved.iterdir(), key=lambda e: e.name):
                # Skip hidden files or tests if needed
                is_dir = entry.is_dir()
                try:
                    stat = entry.stat()
                except FileNotFoundError:
                    continue
                name = entry.name
                size = self._human_size(stat.st_size) if not is_dir else "-"
                mtime = (
                    datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    if stat.st_mtime
                    else ""
                )
                items.append(
                    {
                        "name": name,
                        "type": "directory" if is_dir else "file",
                        "size": size,
                        "raw_size": stat.st_size if not is_dir else 0,
                        "last_modified": mtime,
                        "path": relative_path + "/" + name if relative_path else name,
                        "is_dir": is_dir,
                        "download_url": f"/api/storages/{self.storage_id}/download?path={self._url_path(relative_path, name)}",
                    }
                )
        except PermissionError as exc:
            raise InsufficientPermissionsError(f"Cannot browse {resolved}: {exc}")
        return items

    def download_file(self, relative_path: str) -> Path:
        resolved = self.validate_path(relative_path)
        if not resolved.is_file():
            raise StorageError(f"Not a file: {relative_path}")
        return resolved

    def upload_file(self, relative_path: str, data: bytes | None = None) -> dict[str, Any]:
        if self.is_readonly:
            raise StorageError("Cannot upload to read-only storage.")
        resolved = self.validate_path(relative_path)
        if resolved.exists() and not resolved.is_dir():
            raise StorageError(f"File already exists: {relative_path}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            resolved.write_bytes(data)
        return {"status": "uploaded", "path": relative_path, "size": len(data) if data else 0}

    def create_dir(self, relative_path: str) -> Path:
        if self.is_readonly:
            raise StorageError("Cannot create directory in read-only storage.")
        resolved = self.validate_path(relative_path)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def rename(self, old_rel: str, new_rel: str) -> Path:
        if self.is_readonly:
            raise StorageError("Cannot rename in read-only storage.")
        resolved_old = self.validate_path(old_rel)
        resolved_new = self.validate_path(new_rel)
        if resolved_new.exists():
            raise StorageError(f"Target already exists: {new_rel}")
        resolved_old.rename(resolved_new)
        return resolved_new

    def delete(self, relative_path: str) -> None:
        if self.is_readonly:
            raise StorageError("Cannot delete from read-only storage.")
        resolved = self.validate_path(relative_path)
        if resolved.is_dir():
            if any(resolved.iterdir()):
                raise StorageError("Directory not empty.")
            resolved.rmdir()
        else:
            resolved.unlink()

    def test_connection(self) -> dict[str, Any]:
        try:
            root = self.resolved_root
            if not root.exists():
                return {"status": "unavailable", "reason": "root directory missing"}
            if self.is_readonly:
                return {"status": "read_only", "root": str(root)}
            test_file = root / ".groot_test_write"
            try:
                test_file.touch()
                test_file.unlink()
                return {"status": "ok", "root": str(root)}
            except PermissionError:
                return {"status": "read_only", "reason": "cannot write to root"}
        except Exception as exc:
            return {"status": "error", "reason": str(exc)}

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _url_path(self, relative_path: str, name: str) -> str:
        if relative_path:
            return f"{relative_path}/{name}"
        return name


class MountedSMBStorageAdapter(LocalStorageAdapter):
    @property
    def storage_type(self) -> str:
        return "smb"


class MountedNFSStorageAdapter(LocalStorageAdapter):
    @property
    def storage_type(self) -> str:
        return "nfs"
