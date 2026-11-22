"""Validate the external storage path before storage-dependent work starts."""

import os
from pathlib import Path


class StorageConfigurationError(ValueError):
    """The configured model/data storage cannot be used."""


def validate_storage_root(raw_path: str | None) -> Path:
    """Return a usable absolute directory; never default to an internal disk."""
    if not raw_path or not raw_path.strip():
        raise StorageConfigurationError("AI_SINGER_STORAGE_ROOT is not configured.")

    root = Path(raw_path.strip()).expanduser()
    if not root.is_absolute():
        raise StorageConfigurationError("AI_SINGER_STORAGE_ROOT must be an absolute path.")
    if not root.is_dir():
        raise StorageConfigurationError(
            "AI Singer storage is unavailable. Connect the external drive and check AI_SINGER_STORAGE_ROOT."
        )
    if not os.access(root, os.W_OK):
        raise StorageConfigurationError(
            "AI Singer storage is not writable. Check the folder permissions."
        )
    return root


def configured_storage_root() -> Path:
    """Read current configuration on each check, including after drive reconnects."""
    return validate_storage_root(os.environ.get("AI_SINGER_STORAGE_ROOT"))
