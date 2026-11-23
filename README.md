# AI Singer

AI Singer is a planned interactive AI singing studio in which a music director sings a melody, waits for the AI to listen and analyze it, then hears it reproduced by a selectable male or female AI singing voice. The director can correct sections or request optional creative alternatives.

**Current status:** CPU-based YIN and RMVPE analysis and a local Pitch Lab visual comparison page. RMVPE inference has run successfully on the user's Windows machine; stable-note segmentation and octave review remain experimental. No full React studio, singing voice model, training, lyrics interpretation or conversational agent.

## Intended experience

1. Sing a phrase and finish recording (explicit Done Singing action; optional automatic end detection).
2. Analyze pitch, rhythm, timing, pauses, and vocal expression.
3. Render an attempt in a chosen, permissioned singing voice.
4. Compare the output and explain any measurable differences or uncertainty.
5. Accept Telugu or English corrections, revise targeted sections, and save approved takes.
6. Offer optional alternative performances in Collaborative Mode without overwriting the director's preferred take.

## Development handoff

Read [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) **first** in every new development session, then verify its statements against the actual files and Git history. It records the project scope, proposed stack, architecture, current progress, testing, HDD plan, and next tasks.

The user's Windows toolchain and disk capacity were reviewed from supplied PowerShell output. The user confirmed that the Seagate external HDD is the exFAT volume labeled **Dimpu**, currently **D:**. Its folders are not created until the script below is run on the laptop.

## Repository rules

Keep stable work on `main`; create a short-lived feature branch or PR only when review or isolation adds value. Review changes and tests before pushing. Never commit credentials, recordings, model weights, datasets, caches, or generated outputs. Keep large assets in configurable local storage rather than Git.

## Seagate storage setup (Windows)

The user-confirmed Seagate external HDD is the 2 TB exFAT volume labeled **Dimpu**, currently assigned `D:`. Store large model files, datasets, caches, checkpoints and generated audio under `D:\AI_Singer`. The script resolves the volume **by label**, so it does not rely on a fixed drive letter.

From PowerShell, clone the repository if needed (or `git pull --ff-only` in an existing clone), then run:

```powershell
git clone https://github.com/Nithin0553/AI-Singer.git
cd AI-Singer
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu' -Preview
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
$env:AI_SINGER_STORAGE_ROOT
```

**Preview** is read-only. The second command creates only AI Singer project folders if missing and sets `AI_SINGER_STORAGE_ROOT`, `HF_HOME`, and `TORCH_HOME` in the **current PowerShell session**. It does not format disks, download files, or change system-wide environment variables.

Re-run the script in each new PowerShell session or after reconnecting the HDD. If the label is absent or ambiguous, it stops rather than guessing. The user has reported successful storage setup on their Windows laptop.

## Minimal backend quick start (Windows)

In the **same PowerShell window** where storage was configured:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Open `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/ready`. The first checks API liveness, and the second requires the configured storage directory. The endpoints do not download or load models.

The original 9 tests passed on the user's Windows laptop. The pre-change 41-test suite passed in the isolated development environment and still needs testing on Windows Python 3.12. See `PROJECT_CONTEXT.md`.

## Stage 1: analyze a completed vocal phrase

The experimental `POST /analyze` endpoint accepts a **1–15-second** finished audio clip, decodes it through **FFmpeg** using a short-lived, seekable temporary file (WAV and M4A tested synthetically), and estimates pitch (Hz + MIDI), stable note candidates and low-volume intervals. Results are returned as JSON. The API is CPU-only, does not download model weights, and does not intentionally save uploads in the project storage directory.

On Windows, from the root of your **existing clone** in a PowerShell terminal:

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Open `http://127.0.0.1:8000/docs`, expand **POST /analyze**, choose **Try it out**, upload a clear solo vocal recording, then choose **Execute**. Return JSON includes `duration_seconds`, `sample_rate_hz`, `hop_seconds`, `pitch_track`, `note_events`, `quiet_intervals` and `warnings`. Audio is limited to **10 MiB**; 1–15 seconds are accepted. Upload failures return HTTP 422; FFmpeg missing from PATH returns HTTP 503.

The decoder now uses a **temporary seekable file** instead of piping the upload into FFmpeg. This improves compatibility with M4A/MP4 recordings that require seeking; the temporary file is automatically deleted after processing. The uploaded filename is not used as a disk path. This change was tested with FFmpeg-generated AAC/M4A files, but the specific user recording still requires a Windows retest. `GET /analyze` returns HTTP 405 by design; submit files using **POST /analyze** in Swagger.

**Experimental limitation:** These are heuristic measurements, **not** verified notes, accurate lyrics, beat transcription, or an AI singer rendering. Onsets, rests, glissando, ornaments, noise and vocal breaths may be wrong. Real microphone recordings must be evaluated next. There is no plotted musical score or generated singing yet.


## Optional RMVPE neural pitch comparison

YIN remains the default for `POST /analyze`. Select `POST /analyze?estimator=rmvpe` to try **RMVPE via ONNX Runtime CPU**. The neural estimator is optional and **never automatically downloads weights**. If the checkpoint or optional dependency is missing, the endpoint returns HTTP 503 without disrupting YIN.

On the Windows laptop, from the project root:

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev,rmvpe]"
.\.venv\Scripts\python -m pytest -q
```

After reviewing the checkpoint source and rights for your intended use, manually download the canonical `rmvpe.onnx` to the Seagate drive. The existing folder is created by the storage initializer:

```powershell
$model = Join-Path $env:AI_SINGER_STORAGE_ROOT 'models\audio_analysis\rmvpe.onnx'
if (-not (Test-Path $model)) {
    Invoke-WebRequest -Uri 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.onnx?download=true' -OutFile $model
}
(Get-FileHash -Algorithm SHA256 $model).Hash.ToLower()
```

Expected SHA-256: `5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd`. The adapter rejects mismatched weights and uses CPU by default. An existing compatible checkpoint may be selected through absolute `AI_SINGER_RMVPE_MODEL`, but it must match the canonical checksum.

Benchmark the same 1–15-second solo clip through both algorithms:

```powershell
$clip = 'C:\path\to\Test 1.m4a' # Replace with your recording's actual location
$report = Join-Path $env:AI_SINGER_STORAGE_ROOT 'outputs\previews\yin-rmvpe-comparison.json'
.\.venv\Scripts\python -m ai_singer.pitch_benchmark "$clip" --output "$report"
```

The result includes both pitch contours, runtime, voiced-frame overlap, median **difference between algorithms** in cents, and octave-like disagreements. **Agreement is not ground-truth accuracy**. Neither estimator has been benchmarked with the actual RMVPE checkpoint on the user's Windows system yet.

Source: <https://github.com/NewComer00/rmvpe-onnx> (Python API, checkpoint URL and hash). Verify third-party code/model distribution and commercial-use rights before production.

## Pitch Lab — experimental musical review

The backend now serves a local visualization page at **http://127.0.0.1:8000/pitch-lab**. In the PowerShell session that will run the API:

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pip install -e ".[dev,rmvpe]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Upload a completed 1–15-second phrase. Choose **Compare YIN + RMVPE**, **YIN only** (no checkpoint required), or **RMVPE only**. Pitch Lab displays both measured contours, approximate stable pitch cores, and reviewable disagreement intervals. Use the built-in audio player and click the graph to seek the selected recording. The results may be saved as JSON locally; recordings are not intentionally saved permanently by this API.

The existing `POST /analyze` continues to return `pitch_track` but its `note_events` now represent **stable pitch cores**, not every quantized pitch fluctuation. New fields `pitch_transitions` and `octave_jump_candidates` distinguish glides and suspicious octave excursions. No raw pitch measurements are automatically corrected. The new `POST /compare` returns both analyses and groups continuous disagreements for review. A missing RMVPE checkpoint returns HTTP 503 in comparison mode; YIN-only remains usable.

**Reference evaluation (optional):** To measure actual accuracy, annotate an independent known-pitch reference as `backend/examples/pitch-reference.example.json` shows. Each segment needs a start, end and MIDI note, or `null` for an explicitly known rest. From `backend/`:

```powershell
.\.venv\Scripts\python -m ai_singer.pitch_validation "$report" "C:\path\to\my-reference.json"
```

Here `$report` is the saved JSON from `python -m ai_singer.pitch_benchmark` on the *same* recording. The evaluator reports median absolute pitch error (cents), missed voiced frames, voiced frames inside annotated silence, and octave-like errors. It **excludes unlabeled intervals**. Do not use the example annotations with unrelated singing or treat agreement between two estimators as ground truth.

**Validation status:** A development-container mirror passed 67 tests covering musical glides, steady pitches, short vs sustained octave changes, API uploads, reference metrics and the visual page. The final GitHub file tree and user Windows run still need independent acceptance; no actual user recording or known-note annotations were supplied for musical ground truth.
