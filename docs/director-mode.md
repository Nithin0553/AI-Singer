# AI Singer — Director Mode take library (Milestone 1)

Director Mode is the first persistent, human-directed singing review experience. It is not yet a language-understanding agent or a region-based repair system. It stores separate original and generated recordings, supports full-phrase re-renders, approval, and time-specific notes for future refinement.

## How to use

1. Start your existing AI Singer backend with the same external storage/RVC environment. Continue using only properly authorized voices; Shadowww T02 is **CC BY-NC 4.0, noncommercial and attribution-required**.
2. In [Voice Lab](http://127.0.0.1:8000/voice-lab), upload a 1–15-second vocal and render it. Normal previews are temporary, not saved.
3. Click **Save as Director session** only when you choose to retain the performance. This copies the **exact uploaded original audio bytes** and the converted 16-bit PCM WAV into a new external-drive session.
4. Open [Director Mode](http://127.0.0.1:8000/director). Select any saved session, compare the original and selected converted take, choose another take or download the WAV. The +0–9 dB slider boosts **browser playback only**, not stored files/downloads; high boosts may clip.
5. **Approve selected take** stores its ID without changing or overwriting the original or any take.
6. Choose a time range, write an English or Telugu correction note, and save. The note is marked **pending_review** and can later be clicked to seek the passage. **It is not yet executed by AI**.
7. **Re-render full phrase as a new take** runs the RVC engine again using the saved **original**, appending a new WAV without replacing prior takes or their approvals. The current RVC adapter does not apply feedback or guarantee a musically different interpretation.

## External HDD storage

The backend uses the configured AI_SINGER_STORAGE_ROOT only (the Dimpu drive in the user's current setup). A user-initiated save creates:

```text
<AI_SINGER_STORAGE_ROOT>/outputs/director_sessions/
  <generated-session-id>/
    session.json
    original.m4a                 # or WAV, MP3, WebM, Ogg, FLAC
    take_<generated-take-id>.wav
```

Source format is detected from audio bytes, not a user-uploaded filename. The **original is saved unchanged**; decoding is used only for duration validation. Converted WAV files are checked for mono PCM16, sample rate, completeness, and time alignment (within 1.5 seconds of the source). The JSON metadata contains only relative IDs, duration, voice ID, take history, approval pointer and correction notes—no model paths or recording filenames. Metadata changes are atomic, and if saving a new take fails its unreferenced file is rolled back.

**Limits:** 30 sessions; 12 takes per session; 100 feedback notes per session; 300 characters per note; 10 MiB original upload; 25 MiB converted WAV; strict generated session/take IDs and symlink escape protection. No server-side delete/retention policy is implemented: saved recordings remain until the user deliberately removes them from external storage.

This is a **single-user localhost** design using a process-local lock, not a public production service. Do not expose Uvicorn publicly or use several workers with one folder without authorization and cross-process locks.

## API

| Method and route | Action |
| --- | --- |
| GET /director | Director Mode page |
| GET /director/sessions | Session list |
| POST /director/sessions | Explicitly save source, converted WAV and authorized voice |
| GET /director/sessions/{id} | Session and review history |
| GET /director/sessions/{id}/original | Exact source recording |
| GET /director/sessions/{id}/takes/{take_id}.wav | A saved converted take |
| POST /director/sessions/{id}/approve | Set approved take ID |
| POST /director/sessions/{id}/feedback | Record a timed instruction note |
| POST /director/sessions/{id}/render | Re-render **full source** and append a take |

## Windows acceptance

```powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pytest -q tests/test_director_sessions.py tests/test_voice_render.py
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
```

Ensure AI_SINGER_RVC_ROOT and AI_SINGER_RVC_PYTHON still point to the reviewed working RVC environment **in the same PowerShell session**. The first RVC neural conversion succeeded previously; **new Director Mode behavior and its full Windows tests are not yet user-verified**.

**Next milestone:** region-boundary-safe targeted regeneration and AI/director feedback understanding. Current notes are review metadata, not automatic musical instructions to the synthesis model.

## Milestone 2 — explicit passage corrections

A separate, supported **Apply a bounded passage correction** section is now available in Director Mode. Select a saved take and start/end time, choose a pitch shift in semitones or volume adjustment in dB, and click **Create candidate take**. Only audio within the region is modified, with a short 45-ms internal crossfade; the original audio, prior takes, approval pointer and samples outside the selected interval are preserved. New takes record their source-take ID and numeric edit recipe.

Saved feedback notes offer a **Use this interval** shortcut to fill the time fields, but the program does **not** parse the instruction text or perform a new neural singing interpretation. See [Passage corrections](passage-corrections.md) for numeric limits, endpoint, tests and caveats. This milestone is code-implemented and DSP-tested; full Windows/browser testing remains pending.

### Audible passage selection and A/B review

If editing produces a new take but no obvious audible difference, verify the selected start/end timestamps. Earlier Director Mode versions defaulted to `0.00–1.00s`, which in the first 12.46-second test vocal is considerably quieter than the middle of the performance. The current interface suggests a **strongest two-second RMS interval** when first loading a take, offers **Find an audible passage**, and adds an A/B panel for each edited take's original parent vs resulting WAV over **only the edited time range**. It also reports measured signal changes and warns on relatively quiet selections. Loudness is a heuristic, not a voice classifier. Corrections remain explicit DSP operations, not AI interpretation of text.
