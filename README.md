# AI Singer

AI Singer is a planned interactive AI singing studio in which a music director sings a melody, waits for the AI to listen and analyze it, then hears it reproduced by a selectable male or female AI singing voice. The director can correct sections or request optional creative alternatives.

**Current status:** YIN/RMVPE Pitch Lab and a working local RVC voice-conversion preview. A genuine first neural WAV was successfully generated on the user's Windows RTX 3050 Ti with an authorized noncommercial Shadowww T02 voice. **Director Mode Milestone 1** adds optional external-drive session/take persistence, approval and timed feedback notes; Windows acceptance is pending. Automated targeted revisions, language-aware music direction, training and full React studio are not yet implemented.

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

## Synthetic ground-truth calibration

Generate a **7.55-second, known-pitch WAV** with A3 (220 Hz), C4 (261.63 Hz), a continuous upward C4-to-D4 slide, D4 (293.66 Hz), A3 again, and pauses. The supplied reference labels only held-note interiors and confirmed silence; slide and onset transitions are excluded from constant-note scoring.

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ai_singer.calibration --compare
```

The command writes **only to the configured external storage** at `outputs/previews/calibration/`:

- `known-pitch-calibration.wav`: audio for `/pitch-lab`.
- `known-pitch-reference.json`: independent reference pitches and rests.
- `known-pitch-comparison.json`: full YIN/RMVPE analysis.
- `known-pitch-scores.json`: pitch error, voiced coverage, silence mistakes and octave errors against known references.

Without `--compare`, it generates the audio/reference without loading RMVPE. It does not download weights. Existing audio/reference files are reused; use `--overwrite` only when explicitly regenerating. The script refuses to fall back to an unconfigured internal drive.

**Important:** A strong synthetic benchmark score is not evidence of accuracy on **human singing**. For that next test, independently annotate pitches and note timings actually sung rather than scoring a human recording against these synthetic timestamps.

### Slow-glide interpretation fix

The original pitch detector remains unchanged. Musical event grouping now checks pitch movement over a longer interval as well as local stability, so a gentle C4-to-D4 slide is not mislabeled as one long C♯4. Both estimators' uploaded calibration tracks now produce **A3, C4, D4, A3** stable cores with an intervening upward glide candidate. Events are still *approximate*, not confirmed notes or onsets in human performances. No weights or new dependencies are required.

To verify the change locally, run `git pull --ff-only`, then `.\\.venv\\Scripts\\python -m pytest -q` from `backend/`; restart the API before rerunning Pitch Lab. The exact Windows test result for this fix remains pending.

### Reviewing voicing differences

In **Compare YIN + RMVPE** mode, Pitch Lab now distinguishes:
- **Red bands:** pitch disagreement (or octave-like disagreement) when both models report a pitch.
- **Amber bands:** RMVPE reports pitch but YIN does not.
- **Light-blue bands:** YIN reports pitch but RMVPE does not.

The new comparison JSON keeps the original `agreement.disagreement_intervals` unchanged and adds `voicing_disagreement_intervals`, `rmvpe_only_voiced_frames`, and `yin_only_voiced_frames`. Click a colored band on the plot or a listed time range under **Voicing differences** to seek and listen to the original recording. Each span indicates **a model disagreement**, not which model is correct. Short one-frame differences remain visible, though they can reflect uncertainty around an onset.

Re-analyze your original `Test 2.m4a` using the new version. The expected comparison from the previously uploaded report has **23 RMVPE-only voiced frames** and **1 YIN-only**, grouped into **six intervals**, including **6.16–6.36 s** and **9.26–9.38 s**. These are not independently verified correct pitches or sung-note boundaries. No model weights or new dependencies are needed.

## Manual performance annotations in Pitch Lab

The local Pitch Lab now includes **Mark your performance** beneath the original pitch comparison. This is intended for independently checked reference notes, not automatically inferred model predictions.

1. Upload a finished 1–15-second recording and select **Analyze**. Listen to the original recording using the built-in player.
2. Choose **Held note**, **Quiet / rest**, or **Glide**. Enter a start/end timestamp, or seek the player and use **Start at playhead** / **End at playhead**.
3. For held notes, enter a **known MIDI note** (for example A3=57, C4=60) measured from an independent reference. Label only a stable interior interval; do not assume your actual sung note perfectly matches an intended piano note. For glides choose Up / Down / Unknown. Do not overlap labels.
4. **Add interval**, then listen/edit/remove each entry. Use **Save reference JSON** to download your labels and **Load reference JSON** to resume a previous session. Importing labels does not prove they belong to the currently selected recording; check the timing.
5. Choose **Score against labels** to evaluate each available YIN/RMVPE track. The API returns detected/expected held-note frames, missed pitched frames, pitches detected during labeled rests, median absolute deviation in cents, and separate glide direction reviews. Unlabeled time is excluded from note/rest scoring. The glide is **not** scored as a held note. After scoring, select **Save accuracy report JSON** to download the manually entered labels and both model evaluation summaries in `ai-singer-manual-scores.json` (no audio). This combined report can also be imported again using **Load reference JSON**.

**Privacy and evaluation limits:** Audio is processed as before; reference labels remain in the browser unless you explicitly export JSON or submit them to the local scoring endpoint. The backend does not persist annotations or audio in this operation. The result states \`manual_unverified\`, because manually entering a note is not independent proof that the singer actually performed that pitch. For true accuracy, obtain a separately confirmed reference (e.g., an instrument/reference tone and carefully audited performed-pitch annotation). This milestone does not add voice synthesis, lyric recognition or an autonomous musical director.

**Windows verification (existing installation, no new models/dependencies):**

\`\`\`powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
\`\`\`

After the server starts, open \`http://127.0.0.1:8000/pitch-lab\` and test marking/importing/exporting/scoring references. Original raw pitch tracks, red pitch review and amber/light-blue voicing-review markers are unchanged.

## First singing voice output: Voice Lab

Development has moved beyond pitch calibration to an **opt-in, local RVC voice-conversion preview**. The source singer supplies melody and timing; a separately installed, authorized target voice model changes vocal timbre. This is not text-to-song generation or a trained autonomous musical director, and the first voice output still requires a real checkpoint.

Start the existing server, then open <http://127.0.0.1:8000/voice-lab> (also linked from Pitch Lab). Upload a finished solo recording, choose a ready voice profile from your Seagate drive, confirm you have permission for both the recording and voice model, render, then listen and download a WAV. Added endpoints: GET /voices and POST /render-voice; the existing analysis and annotation endpoints remain unchanged.

**Before a real conversion:** Read [the separate RVC/authorized voice setup guide](docs/voice-render.md) and use backend/examples/voice-profiles.example.json as a disabled-by-default manifest template. Configure the independent RVC CLI Python runtime with AI_SINGER_RVC_ROOT and AI_SINGER_RVC_PYTHON; keep checkpoints under AI_SINGER_STORAGE_ROOT/models/voice_conversion. No training data, third-party weights, or preapproved male/female voices are included. Never enable a checkpoint without confirming permissions and provenance.

**Verification update:** The RVC integration was initially contract-tested with a fake subprocess. The user subsequently installed Shadowww T02 and an official RVC runtime and confirmed **a real successful neural voice-conversion WAV** from their Windows laptop. Universal fidelity and further musicianship capabilities remain unverified; no routine pitch calibration is required to continue.

### First noncommercial demo voice — Shadowww T02

We've selected [Shadowww T02](https://huggingface.co/ShadowSH2306/shadowww-voices) as an **explicitly noncommercial RVC v2 prototype voice** (publisher terms: CC BY-NC 4.0, attribution required). It is a low/natural voice, not a Shreya imitation and not a licensed commercial-release voice.

A safe, optional, checksum-verifying installation command is documented in [Voice Lab model setup](docs/voice-render.md#first-noncommercial-demo-model-shadowww-t02). It installs `shadowww-t02.pth` and the `voices.json` profile under the existing external drive, only if you accept the noncommercial license. It leaves your models and earlier source recordings alone and installs **no RVC runtime**. Real conversion has now succeeded on the user's configured Windows laptop. This checkpoint remains restricted to properly credited, noncommercial demos.

## Director Mode — versioned singing takes

**New local interface:** <http://127.0.0.1:8000/director>. After a successful authorized Voice Lab conversion, click **Save as Director session** to explicitly preserve the original source bytes and converted WAV under `AI_SINGER_STORAGE_ROOT/outputs/director_sessions/` on the external drive.

Director Mode lets you open a saved session, listen to original and converted takes, adjust playback-only gain (+0 to +9 dB), approve a selected take, add Telugu/English time-range feedback notes, and generate another **full-phrase** RVC take from the saved original without overwriting prior work. Correction notes are **not interpreted or applied automatically yet**. Saved audio persists until the user deliberately removes it; ordinary Voice Lab previews remain ephemeral. This is an opt-in localhost, single-user workflow.

Read [Director Mode behavior, data safety and acceptance steps](docs/director-mode.md). New tests: `backend/tests/test_director_sessions.py`. Windows acceptance of this milestone is pending; the earlier successful RVC preview is already confirmed.
