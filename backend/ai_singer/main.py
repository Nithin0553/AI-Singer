"""AI Singer API: health, external storage readiness, and vocal phrase analysis."""

from fastapi import FastAPI, File, HTTPException, UploadFile

from ai_singer.audio_analysis import (
    MAX_UPLOAD_BYTES,
    AudioDecoderUnavailable,
    AudioInputError,
    analyze_audio,
    decode_audio,
)
from ai_singer.storage import StorageConfigurationError, configured_storage_root

app = FastAPI(title="AI Singer API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness is independent of model downloads and connected drives."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Reject storage-dependent work when the configured drive is absent."""
    try:
        configured_storage_root()
    except StorageConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"status": "ready", "storage": "available"}


@app.post("/analyze")
def analyze(file: UploadFile = File(...)) -> dict:
    """Analyze a finished 1–15-second phrase without storing the uploaded audio."""
    try:
        recording = file.file.read(MAX_UPLOAD_BYTES + 1)
        samples = decode_audio(recording)
        return analyze_audio(samples)
    except AudioInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except AudioDecoderUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        file.file.close()
