# AI Singer

AI Singer is a planned interactive AI singing studio in which a music director sings a melody, waits for the AI to listen and analyze it, then hears it reproduced by a selectable male or female AI singing voice. The director can correct sections or request optional creative alternatives.

**Current status:** Minimal FastAPI backend with a **CPU-only short-phrase musical analysis prototype** and automated tests. No frontend, singing voice model, training, lyrics interpretation, or interactive musical-agent reasoning yet.

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

The original 9 tests passed on the user's Windows laptop. The **expanded 25-test suite** passed in an isolated development environment and still needs testing on their Windows Python 3.12 installation. See `PROJECT_CONTEXT.md`.

## Stage 1: analyze a completed vocal phrase

The experimental `POST /analyze` endpoint accepts a **1–15-second** finished audio clip, decodes it through **FFmpeg 9.1** (WAV recommended for first tests), and estimates pitch (Hz + MIDI), stable note candidates and low-volume intervals. Results are returned as JSON. The API is CPU-only, does not download model weights, and does not intentionally save uploads in the project storage directory.

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

**Experimental limitation:** These are heuristic measurements, **not** verified notes, accurate lyrics, beat transcription, or an AI singer rendering. Onsets, rests, glissando, ornaments, noise and vocal breaths may be wrong. Real microphone recordings must be evaluated next. There is no plotted musical score or generated singing yet.
