"""AI Singer API: process health and external-storage readiness."""

from fastapi import FastAPI, HTTPException

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
