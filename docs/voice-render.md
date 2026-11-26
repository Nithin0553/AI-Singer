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

## First noncommercial demo model: Shadowww T02

The first selected model is **Shadowww T02** from [ShadowSH2306/shadowww-voices](https://huggingface.co/ShadowSH2306/shadowww-voices). The publisher states the source vocals were self-recorded and publishes the RVC v2, 48-kHz model under **CC BY-NC 4.0**. You may experiment noncommercially with attribution, but **cannot use this checkpoint in a commercial product without additional permission**. Label generated vocals as AI; do not claim the publisher performed your recording or impersonate the voice. The publisher also credits **KLM 4.1 by SeungHyun Han (Seoul Streaming Station)** as the pretrained base; its additional terms should be checked before any product release.

The setup command downloads **the individual `shadowww-t02.pth` only** (~57.5 MB), not a ZIP or the retrieval index (our first adapter uses `--index-rate 0`). It pins the model's published SHA-256: `7166e6cc680178a1273929ebe00daedab1f8db8039bec312c96a23093ef2ac20` ([publisher checksum list](https://huggingface.co/ShadowSH2306/shadowww-voices/blob/main/SHA256SUMS)). Model weights are never checked into Git or automatically loaded during installation.

From a **new PowerShell terminal** on the user's Windows laptop:

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only

.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend

# Run without --accept-noncommercial-license to see the terms error instead
# of downloading. Passing it is an affirmative acceptance for research/demo use.
.\.venv\Scripts\python -m ai_singer.install_licensed_voice --install --accept-noncommercial-license

# Confirm checkpoint checksum and local voice registry without loading .pth
.\.venv\Scripts\python -m ai_singer.install_licensed_voice --check

# Confirm the profile is listed (RVC runtime is still needed for inference).
.\.venv\Scripts\python -c "from ai_singer.voice_render import list_voices; print(list_voices())"
```

The installer uses only Python's standard library, streams from the known publisher's Hugging Face URL, limits the file to 80 MiB, checks SHA-256 **before** moving the checkpoint into the model directory, and preserves other voice entries in `voices.json`. Existing files with mismatching checksums are not overwritten; invalid manifests and symlink escapes are refused. It writes locally under `<AI_SINGER_STORAGE_ROOT>/models/voice_conversion/shadowww-t02/shadowww-t02.pth` and registers the profile with the published license, attribution and source. `--check` does not use the network.

**Important:** This only prepares the approved demo checkpoint. `voice_lab_ready: true` means the **profile and model file** are configured, *not* that a separate RVC inference runtime, HuBERT, ContentVec and RMVPE files are installed or tested. Set up the RVC CLI using the instructions above, and verify its `infer/cli.py --help` arguments before launching Voice Lab. RVC `.pth` loading may execute unsafe serialized code; checksum verification does **not** make external model execution safe. Keep this model restricted to a noncommercial, credited and clearly AI-labeled local prototype.

## Verified next step: RVC runtime for Windows RTX 3050 Ti

As of 2026-11-26, the user's model check confirms Shadowww T02 has a verified checksum and is registered in Voice Lab. The same check reports rvc_runtime_installed = not_checked. That field is not an RVC runtime test; installing this checkpoint is distinct from configuring the third-party RVC engine.

Official upstream sources reviewed: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md and https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/cli.md. RVC source main was 81eed5e8f68b6bed1789f682fe78cdd324495afc. Its CLI supports our adapter flags. For Windows / Python 3.12 / pre-RTX-50 NVIDIA GPUs, it specifies Torch 2.7.1+cu118 and the literally named file requirments_cu118_py312.txt.

### Create a dedicated RVC environment on Dimpu

~~~powershell
cd C:\Users\nithi\AI-Singer
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
$rvc = Join-Path $env:AI_SINGER_STORAGE_ROOT 'runtime\rvc'
New-Item -ItemType Directory -Force (Split-Path $rvc) | Out-Null

if (-not (Test-Path (Join-Path $rvc 'infer\cli.py'))) {
    if (Test-Path $rvc) { throw "RVC folder exists without infer\cli.py; inspect it first." }
    git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git $rvc
}
Set-Location $rvc
if (-not (Test-Path '.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
$py = Join-Path $rvc '.venv\Scripts\python.exe'
& $py --version
& $py -m pip install --upgrade pip wheel
~~~

### Install the official NVIDIA dependencies and verify CUDA

~~~powershell
& $py -m pip install 'torch==2.7.1+cu118' 'torchaudio==2.7.1+cu118' --index-url https://download.pytorch.org/whl/cu118 --extra-index-url https://pypi.org/simple
& $py -m pip install -r .\requirments_cu118_py312.txt
& $py -c "import torch; print(torch.__version__); print('CUDA:',torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
~~~

The upstream requirements file explicitly points to a third-party PyPI mirror. Review it before installing, or change only its package-index URLs to the official indexes following the upstream README. RVC and other model dependencies execute third-party software.

### Download official assets needed for inference

~~~powershell
& $py -m pip install 'huggingface_hub>=0.34,<1'
$hf = Join-Path $rvc '.venv\Scripts\hf.exe'
& $hf download lj1995/VoiceConversionWebUI --revision main --include 'hubert_base/*' --local-dir assets
& $hf download lj1995/VoiceConversionWebUI rmvpe.pt --revision main --local-dir assets/rmvpe

Test-Path '.\assets\hubert_base\config.json'
Test-Path '.\assets\hubert_base\preprocessor_config.json'
Test-Path '.\assets\hubert_base\pytorch_model.bin'
Test-Path '.\assets\rmvpe\rmvpe.pt'
& $py .\infer\cli.py --help
~~~

The four checks must print True. These RVC HuBERT/ContentVec and RMVPE files are separate from AI Singer's ONNX pitch model. Training-only pretrained checkpoints, mute.zip and index files are unnecessary for our first index-rate 0 conversion.

### Connect RVC to Voice Lab

~~~powershell
$env:AI_SINGER_RVC_ROOT = $rvc
$env:AI_SINGER_RVC_PYTHON = $py
cd C:\Users\nithi\AI-Singer\backend
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
~~~

Then open http://127.0.0.1:8000/voice-lab and try a permitted original vocal with Shadowww T02. On the first run, a 4-GiB GPU may encounter memory constraints; voice quality and compatibility remain unverified until a real output is rendered and listened to. The local model checker will continue to say not_checked for the RVC runtime even after the runtime is installed because it intentionally only checks the voice checkpoint and manifest.

## Troubleshooting the first RVC HTTP 502

If GET /voice-lab and GET /voices succeed but POST /render-voice returns HTTP 502, the child RVC process may have exited without producing a WAV. The browser intentionally hides its third-party output; the root cause is **not** identified by the 502 alone.

First check the checkpoint metadata without a vocal recording:

~~~powershell
cd D:\AI_Singer\runtime\rvc
$py = 'D:\AI_Singer\runtime\rvc\.venv\Scripts\python.exe'
& $py .\infer\cli.py --model 'D:\AI_Singer\models\voice_conversion\shadowww-t02\shadowww-t02.pth' --list-speakers
~~~

If this command fails, the displayed exception is the first issue to resolve. It exercises model checkpoint loading but **not** actual conversion. Do not blindly alter PyTorch weights-only deserialization or install unrelated models based only on HTTP 502.

For a failure occurring after metadata loading, use opt-in local RVC error reporting. Stop the current Uvicorn server using Ctrl+C, then in the same PowerShell window:

~~~powershell
$env:AI_SINGER_STORAGE_ROOT = 'D:\AI_Singer'
$env:AI_SINGER_RVC_ROOT = 'D:\AI_Singer\runtime\rvc'
$env:AI_SINGER_RVC_PYTHON = 'D:\AI_Singer\runtime\rvc\.venv\Scripts\python.exe'
$env:AI_SINGER_RVC_DEBUG = '1'
cd C:\Users\nithi\AI-Singer\backend
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
~~~

After retrying a permitted original vocal in Voice Lab, the local terminal logs the RVC exit code and up to the last 2,500 characters of each captured stdout/stderr stream. These details are **never included in HTTP responses or persisted to a log file by AI Singer**. RVC may print private paths or details: redact sensitive content before posting terminal output. Disable verbose logging later by stopping the server, running Remove-Item Env:\AI_SINGER_RVC_DEBUG -ErrorAction SilentlyContinue, and restarting.

Possible failures include checkpoint format/serialization, unsupported packages, a missing runtime component or CUDA out-of-memory on the 4-GiB GPU. None should be presumed until the concrete CLI error is obtained.
