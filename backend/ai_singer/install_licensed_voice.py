"""Install one publisher-licensed RVC checkpoint for local, noncommercial testing.

No model is loaded/deserialized here. This installs weights, not an RVC runtime.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from ai_singer.storage import configured_storage_root

VOICE_ID = "shadowww-t02"
MODEL_NAME = "shadowww-t02.pth"
MODEL_RELATIVE = f"{VOICE_ID}/{MODEL_NAME}"
MODEL_URL = (
    "https://huggingface.co/ShadowSH2306/shadowww-voices/resolve/main/"
    "t02/shadowww-t02.pth?download=true"
)
EXPECTED_SHA256 = "7166e6cc680178a1273929ebe00daedab1f8db8039bec312c96a23093ef2ac20"
MAX_MODEL_BYTES = 80 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
ATTRIBUTION = "Voice model: Shadowww"


class VoiceInstallError(RuntimeError):
    """A download or profile operation could not be completed safely."""


def _paths() -> tuple[Path, Path, Path]:
    root = configured_storage_root().resolve()
    base = root / "models" / "voice_conversion"
    model = base / MODEL_RELATIVE
    if not base.resolve().is_relative_to(root) or not model.resolve().is_relative_to(base.resolve()):
        raise VoiceInstallError("Voice model location escapes external storage.")
    manifest = base / "voices.json"
    if manifest.is_symlink():
        raise VoiceInstallError("Voice manifest must be a regular file, not a symbolic link.")
    return base, model, manifest


def _digest(path: Path) -> str:
    check = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            check.update(chunk)
    return check.hexdigest()


def _existing_manifest(path: Path) -> dict:
    if not path.exists():
        return {"voices": []}
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise VoiceInstallError("Existing voice manifest is not a valid-sized file.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VoiceInstallError("Existing voice manifest is not valid JSON; it was not changed.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("voices"), list):
        raise VoiceInstallError("Existing voice manifest has no valid voices array.")
    if len(data["voices"]) > 20 or any(not isinstance(p, dict) for p in data["voices"]):
        raise VoiceInstallError("Existing voice manifest has invalid entries.")
    return data


def _register(manifest: Path) -> None:
    data = _existing_manifest(manifest)
    matches = [entry for entry in data["voices"] if entry.get("id") == VOICE_ID]
    if len(matches) > 1 or (matches and matches[0].get("model") != MODEL_RELATIVE):
        raise VoiceInstallError("A conflicting voice ID already exists. Edit it manually instead.")
    if not matches and len(data["voices"]) == 20:
        raise VoiceInstallError("Voice manifest already contains 20 profiles.")
    profile = {
        "id": VOICE_ID,
        "label": "Shadowww T02 — noncommercial demo",
        "model": MODEL_RELATIVE,
        "speaker_id": 0,
        "rights_confirmed": True,
        "enabled": True,
        "license": "CC BY-NC 4.0 — noncommercial only",
        "attribution": ATTRIBUTION,
        "base_attribution": "KLM 4.1 by SeungHyun Han (Seoul Streaming Station)",
        "source": "https://huggingface.co/ShadowSH2306/shadowww-voices",
        "sha256": EXPECTED_SHA256,
    }
    if matches:
        matches[0].update(profile)
    else:
        data["voices"].append(profile)
    contents = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if len(contents.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise VoiceInstallError("Voice manifest would exceed the 64 KiB limit.")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=manifest.parent,
                                         prefix="voices_", suffix=".tmp", delete=False) as out:
            temp_name = out.name
            out.write(contents)
        os.replace(temp_name, manifest)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _download(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix="shadowww_", suffix=".part",
                                         delete=False) as file:
            name = file.name
            with urlopen(Request(MODEL_URL, headers={"User-Agent": "AI-Singer-Local-Installer/1.0"}), timeout=30) as remote:
                digest = hashlib.sha256()
                total = 0
                while True:
                    chunk = remote.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_MODEL_BYTES:
                        raise VoiceInstallError("Downloaded checkpoint exceeds the 80 MiB safety limit.")
                    digest.update(chunk)
                    file.write(chunk)
        if digest.hexdigest() != EXPECTED_SHA256:
            raise VoiceInstallError("Checkpoint SHA-256 does not match publisher's checksum; download discarded.")
        os.replace(name, target)
        name = None
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def install(*, accept_noncommercial_license: bool) -> dict:
    """Download and register T02 only after affirmative acceptance of noncommercial terms."""
    if not accept_noncommercial_license:
        raise VoiceInstallError("Accept CC BY-NC 4.0 noncommercial terms before installing this voice.")
    base, target, manifest = _paths()
    data = _existing_manifest(manifest)  # Fail before download if existing JSON is malformed.
    existing = [r for r in data["voices"] if r.get("id") == VOICE_ID]
    if len(existing) > 1 or (existing and existing[0].get("model") != MODEL_RELATIVE):
        raise VoiceInstallError("A different profile already uses the Shadowww T02 ID.")
    if not existing and len(data["voices"]) == 20:
        raise VoiceInstallError("Voice manifest is full (20 profiles).")
    if target.exists():
        if not target.is_file() or _digest(target) != EXPECTED_SHA256:
            raise VoiceInstallError("An existing file at the target location has the wrong SHA-256; refusing overwrite.")
        reused = True
    else:
        _download(target)
        reused = False
    _register(manifest)
    return {"id": VOICE_ID, "model_path": str(target), "manifest_path": str(manifest),
            "sha256": EXPECTED_SHA256, "reused_existing": reused,
            "license": "CC BY-NC 4.0 (noncommercial only)", "attribution": ATTRIBUTION}


def check() -> dict:
    """Inspect an installation without network access or checkpoint deserialization."""
    _, target, manifest = _paths()
    valid_model = target.is_file() and _digest(target) == EXPECTED_SHA256
    entries = _existing_manifest(manifest)["voices"]
    registered = any(p.get("id") == VOICE_ID and p.get("model") == MODEL_RELATIVE
                     and p.get("enabled") is True and p.get("rights_confirmed") is True
                     for p in entries)
    return {"id": VOICE_ID, "verified_checkpoint": valid_model, "registered": registered,
            "voice_lab_ready": valid_model and registered,
            "rvc_runtime_installed": "not_checked", "model_path": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Download and register T02")
    group.add_argument("--check", action="store_true", help="Inspect previously installed T02")
    parser.add_argument("--accept-noncommercial-license", action="store_true",
                        help="Affirm CC BY-NC 4.0 attribution/noncommercial conditions")
    args = parser.parse_args()
    try:
        result = install(accept_noncommercial_license=args.accept_noncommercial_license) if args.install else check()
    except (VoiceInstallError, OSError, ValueError) as exc:
        parser.exit(1, f"Voice setup failed: {exc}\n")
    print(json.dumps(result, indent=2))
    if args.install:
        print("Attribution: Voice model: Shadowww — AI-generated vocals (noncommercial use only).")
        print("A separate, compatible RVC runtime is still required to render audio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
