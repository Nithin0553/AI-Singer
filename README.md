# AI Singer

AI Singer is a planned interactive AI singing studio in which a music director sings a melody, waits for the AI to listen and analyze it, then hears it reproduced by a selectable male or female AI singing voice. The director can correct sections or request optional creative alternatives.

**Current status:** Minimal FastAPI backend and storage-readiness tests exist. No audio analysis, frontend, singing model, or training has been implemented.

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

Re-run the script in each new PowerShell session or after reconnecting the HDD. If the label is absent or ambiguous, it stops rather than guessing. No action has been run on the user's laptop through the GitHub connection.

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

The existing 9 backend tests passed in an isolated Linux development environment; the PowerShell script and package installation **remain to be verified on the Windows laptop**. See `PROJECT_CONTEXT.md`.
