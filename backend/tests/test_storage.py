from pathlib import Path

import pytest

from ai_singer.storage import StorageConfigurationError, validate_storage_root


def test_storage_root_must_be_configured() -> None:
    with pytest.raises(StorageConfigurationError, match="not configured"):
        validate_storage_root(None)


def test_storage_root_must_be_absolute() -> None:
    with pytest.raises(StorageConfigurationError, match="absolute"):
        validate_storage_root("relative/path")


def test_storage_root_must_exist(tmp_path: Path) -> None:
    with pytest.raises(StorageConfigurationError, match="unavailable"):
        validate_storage_root(str(tmp_path / "disconnected"))


def test_storage_root_must_be_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-directory"
    file_path.touch()
    with pytest.raises(StorageConfigurationError, match="unavailable"):
        validate_storage_root(str(file_path))


def test_storage_root_accepts_directory(tmp_path: Path) -> None:
    assert validate_storage_root(str(tmp_path)) == tmp_path
