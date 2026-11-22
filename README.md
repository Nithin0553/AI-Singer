# AI Singer

AI Singer is a planned interactive AI singing studio in which a music director sings a melody, waits for the AI to listen and analyze it, then hears it reproduced by a selectable male or female AI singing voice. The director can correct sections or request optional creative alternatives.

**Current status:** Documentation-only baseline. No running application, audio pipeline, or trained model exists yet.

## Intended experience

1. Sing a phrase and finish recording (explicit Done Singing action; optional automatic end detection).
2. Analyze pitch, rhythm, timing, pauses, and vocal expression.
3. Render an attempt in a chosen, permissioned singing voice.
4. Compare the output and explain any measurable differences or uncertainty.
5. Accept Telugu or English corrections, revise targeted sections, and save approved takes.
6. Offer optional alternative performances in Collaborative Mode without overwriting the director's preferred take.

## Development handoff

Read [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) **first** in every new development session, then verify its statements against the actual files and Git history. It records the project scope, proposed stack, architecture, current progress, testing, HDD plan, and next tasks.

There are **no installation or run commands yet**. Before configuring the developer's laptop, verify its actual operating system, GPU, toolchain, and internal/external storage.

## Repository rules

Keep stable work on `main`; create a short-lived feature branch or PR only when review or isolation adds value. Review changes and tests before pushing. Never commit credentials, recordings, model weights, datasets, caches, or generated outputs. Keep large assets in configurable local storage rather than Git.

## Minimal backend quick start (Windows)

A minimal FastAPI backend now provides `GET /health` (process liveness) and `GET /ready` (requires a configured, available external storage directory). Musical analysis and singing are **not implemented**.

```powershell
git clone https://github.com/Nithin0553/AI-Singer.git
cd AI-Singer/backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

When the correct external disk and folder are verified, set `AI_SINGER_STORAGE_ROOT` in PowerShell before launching the API, e.g., `$env:AI_SINGER_STORAGE_ROOT = 'X:\AI_Singer'` **after replacing the example with your real location**. Do not use an unverified drive letter or assume that `.env.example` loads automatically. `/ready` intentionally returns HTTP 503 until storage is configured and accessible.

The backend tests passed in the isolated development environment; **Windows-local setup has not yet been verified**. See `PROJECT_CONTEXT.md` for hardware details and next steps.
