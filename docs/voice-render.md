# Voice Lab — authorized RVC conversion preview

This milestone adds an **opt-in voice-to-voice singing preview**, not a text-to-song engine, model trainer, or autonomous musician. It converts a completed 1–15-second solo vocal using a *separately installed* RVC runtime and an independently licensed/consented voice checkpoint. The original voice supplies timing and melody; `--pitch 0` requests no transposition but does not guarantee perfect fidelity.

## One-time setup on Windows

Install and review the [RVC project](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) separately. Use a version whose `infer/cli.py --help` supports `--model`, `--input`, `--output`, `--speaker-id`, `--pitch`, `--f0-method`, and `--index-rate` ([upstream CLI instructions](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/cli.md)). The RVC installation, Python environment, HuBERT and RMVPE assets, and voice model are **not** automatically installed or downloaded by AI Singer. The existing backend Python 3.12 environment is separate.

```powershell
cd C:\Users\nithi\AI-Singer
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'

# Examples only: change to where you installed and reviewed RVC.
$env:AI_SINGER_RVC_ROOT = 'D:\AI_Singer\runtime\rvc'
$env:AI_SINGER_RVC_PYTHON = 'D:\AI_Singer\runtime\rvc\runtime\python.exe'
& $env:AI_SINGER_RVC_PYTHON "$env:AI_SINGER_RVC_ROOT\infer\cli.py" --help
```

The above RVC paths are *not* created or verified by AI Singer. Its own backend and virtual environment stay on the internal disk; the voice models and temporary output live on the Seagate `Dimpu` drive. The RTX 3050 Ti with 4 GiB VRAM may not be sufficient for all model configurations; use a compatible CPU runtime if needed.

## Authorized voice profile

Copy `backend/examples/voice-profiles.example.json` to `<AI_SINGER_STORAGE_ROOT>/models/voice_conversion/voices.json`. The example starts disabled and with `rights_confirmed: false`. Obtain a `.pth` checkpoint from a source with verified permission for training and inference, and place it under `<AI_SINGER_STORAGE_ROOT>/models/voice_conversion/my-licensed-voice/model.pth`. **Only after verifying its permissions**, set `rights_confirmed: true` and `enabled: true` in the manifest. There is no bundled male/female model and no default authorized voice.

Each enabled entry requires a lowercase `id`, `label`, relative `.pth` `model` path, integer `speaker_id` (0–109), and the two approval flags. Absolute/traversal paths are rejected. `.pth` loading can execute arbitrary pickle code; never load an untrusted model.

## Use Voice Lab

Start the existing backend server from the same configured PowerShell session:

```powershell
cd C:\Users\nithi\AI-Singer\backend
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Open <http://127.0.0.1:8000/voice-lab>. Upload a finished solo vocal, select an authorized **ready** profile, confirm permission to use the input and target model, and render. Preview and download the returned WAV. The HTTP endpoints are `GET /voices` and `POST /render-voice` (`file`, `voice_id`, `authorized_use=true`). Existing `/pitch-lab` and analysis remain available.

## What is and isn't verified

The adapter calls the upstream offline RVC CLI with `--pitch 0`, `--f0-method rmvpe` and `--index-rate 0` (no retrieval index required). It uses 16-kHz mono WAV input, a 240-second subprocess timeout, up to 10-MiB input, one render at a time **per process**, and a 25-MiB returned WAV limit. Output duration is checked using FFprobe. Temporary files live under `<AI_SINGER_STORAGE_ROOT>/cache/voice_previews/` and are deleted on normal completion or failure; the server does not keep a persistent voice-take library. Keep Uvicorn on localhost. The adapter sets common offline model-cache environment variables but cannot guarantee arbitrary third-party RVC code makes no network requests.

The tests cover consent, manifest security, temporary-file cleanup, input limits, errors and audio I/O using a **fake RVC script that copies a WAV**, not a trained voice model. Actual RVC inference, singing quality, latency and laptop compatibility are **pending a rights-cleared model and configured runtime**. Do not confuse successful mock tests with genuine neural singing.

HTTP errors: 403 for missing use confirmation, 422 for invalid audio, 429 when a render is in progress, 503 for missing profile/runtime, and 502 for converter or output failure. If conversion fails, inspect the real RVC CLI's local logs; the API does not reveal private paths or third-party error traces.
