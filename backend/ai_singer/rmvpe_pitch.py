"""Optional RMVPE pitch estimation with explicitly managed external model weights."""

from functools import lru_cache
import hashlib
import os
from pathlib import Path

import numpy as np

from ai_singer.storage import StorageConfigurationError, configured_storage_root

# Canonical rmvpe.onnx checksum published by the rmvpe-onnx package.
RMVPE_SHA256 = "5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd"
MODEL_RELATIVE_PATH = Path("models/audio_analysis/rmvpe.onnx")
MIN_CONFIDENCE = 0.03


class RMVPEUnavailable(RuntimeError):
    """The optional estimator cannot run with the current local configuration."""


def model_file() -> Path:
    """Require a real model file; never trigger a package-managed download."""
    override = os.environ.get("AI_SINGER_RMVPE_MODEL")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise RMVPEUnavailable("AI_SINGER_RMVPE_MODEL must be an absolute path.")
    else:
        try:
            path = configured_storage_root() / MODEL_RELATIVE_PATH
        except StorageConfigurationError as exc:
            raise RMVPEUnavailable(str(exc)) from exc
    if not path.is_file():
        raise RMVPEUnavailable(
            "RMVPE weights are not installed. Place the verified rmvpe.onnx under "
            "AI_SINGER_STORAGE_ROOT/models/audio_analysis/ (or set AI_SINGER_RMVPE_MODEL)."
        )
    return path


@lru_cache(maxsize=2)
def _load_model(path: str):
    """Verify canonical model bytes once and reuse the CPU inference session."""
    with open(path, "rb") as checkpoint:
        digest = hashlib.file_digest(checkpoint, "sha256").hexdigest()
    if digest != RMVPE_SHA256:
        raise RMVPEUnavailable("RMVPE weights failed SHA-256 verification; check the model source.")
    try:
        from rmvpe_onnx import RMVPE
    except ImportError as exc:
        raise RMVPEUnavailable(
            'Install the optional dependency with: python -m pip install -e ".[dev,rmvpe]"'
        ) from exc
    try:
        return RMVPE(model_path=path, device="cpu")
    except Exception as exc:
        raise RMVPEUnavailable("RMVPE could not be initialized; check its model and dependencies.") from exc


def estimate_rmvpe(samples: np.ndarray, frame_count: int, sample_rate: int, hop_length: int) -> np.ndarray:
    """Align RMVPE's 10 ms frames to the existing 20 ms output time grid."""
    path = model_file()
    try:
        times, f0, confidence, _ = _load_model(str(path)).predict(samples, sr=sample_rate)
    except RMVPEUnavailable:
        raise
    except Exception as exc:
        raise RMVPEUnavailable("RMVPE inference failed; review the local model installation.") from exc

    times = np.asarray(times, dtype=np.float64)
    f0 = np.asarray(f0, dtype=np.float64)
    confidence = np.asarray(confidence, dtype=np.float64)
    if (times.ndim != 1 or not len(times) or f0.shape != times.shape
            or confidence.shape != times.shape or not np.all(np.isfinite(times))
            or np.any(np.diff(times) <= 0)):
        raise RMVPEUnavailable("RMVPE returned an invalid pitch timeline.")

    target = np.arange(frame_count) * hop_length / sample_rate
    upper = np.searchsorted(times, target).clip(0, len(times) - 1)
    lower = np.maximum(upper - 1, 0)
    closest = np.where(abs(times[lower] - target) <= abs(times[upper] - target), lower, upper)
    aligned = f0[closest].copy()
    valid = (
        (abs(times[closest] - target) <= 0.015)
        & np.isfinite(aligned)
        & (aligned >= 80)
        & (aligned <= 900)
        & np.isfinite(confidence[closest])
        & (confidence[closest] >= MIN_CONFIDENCE)
    )
    return np.where(valid, aligned, np.nan)
