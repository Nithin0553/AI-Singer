# Passage corrections — Director Mode milestone 2

AI Singer can now create **new, non-destructive candidate takes** by changing only a specified interval of an **existing converted WAV take**. This is a deterministic signal-processing feature, **not autonomous language understanding, note-aware singing synthesis, or partial RVC regeneration**.

## How to try it

1. Start the existing local AI Singer server using your configured external `Dimpu` storage. Open <http://127.0.0.1:8000/director>.
2. Choose an existing saved session, then **select the take you want to adjust**. Its audio is never modified in place.
3. Set start/end seconds with the same time controls used for feedback notes, or use **Start at playhead** / **End at playhead**. Saved feedback notes have a **Use this interval** shortcut to populate those time fields. The note text is *not* parsed automatically.
4. In **Apply a bounded passage correction**, choose one of two explicitly supported operations:
   - **Pitch shift:** from −3 to +3 semitones, excluding zero, on a passage from 0.35 through 8 seconds. This moves the entire selected vocal signal's pitch while attempting to preserve duration. It does not know which lyrics, note, or melody interpretation the director intended; formants/timbre may change and artifacts are possible.
   - **Loudness (gain):** from −9 to +9 dB, excluding zero, on a passage at least 0.35 seconds long. Louder gain may clip in the exported audio; listen to the result.
5. Click **Create candidate take**. The backend returns a full-length WAV built from the selected parent, altering only samples inside the selected passage. A 45-ms raised-cosine crossfade is applied **within** that passage at each boundary. No samples before or after the requested interval are modified. The new take is added to your external-drive history and selected for audition; the approved take pointer remains unchanged.
6. Compare the candidate to its source take and original singing. **Approve selected take** only if it sounds correct. The new take includes an edit recipe and its parent's take ID for provenance. Existing approved/original/take recordings are never overwritten.

## Safety and engineering details

- Each operation preserves WAV sample rate, mono channel count, exact PCM frame count and timing. Unaffected regions are **sample-identical** to their source take. Audio is read/produced as mono PCM16, 8–96 kHz, 0.5–18 seconds, 25-MiB maximum.
- Time boundaries use **ceil(start × sample rate)** and **floor(end × sample rate)**, so a rounded time does not accidentally modify neighboring samples. A raised-cosine blend gradually applies the effect inside both edges of the selected region to reduce clicks. This is a DSP crossfade, not perfect perceptual seamlessness; audition transitions.
- The selected take's voice model is inherited in the candidate's metadata; no new RVC model download or GPU operation is needed for these DSP edits. Pitch uses the existing backend's installed `librosa.effects.pitch_shift`; CPU processing may take a few seconds for longer passages.
- User-written feedback remains a separate `pending_review` record. The UI provides a time-range shortcut but does **not** claim to understand or execute Telugu/English instructions.
- Input validation rejects invalid IDs, missing/NaN/nonfinite values, out-of-bounds durations, zero changes, extreme numeric settings, unsupported edit kinds, and attempts to exceed 12 takes per session. A failed edit must not add metadata or overwrite any audio. Metadata saves remain atomic, and failed new-take files roll back.
- Editing an authorized Shadowww T02 take produces a derivative **subject to the same CC BY-NC 4.0 noncommercial / attribution and AI-labeling conditions**. Named-singer Shreya weights remain unapproved and unavailable for this project. Keep the Uvicorn server on localhost and sessions/model files on `Dimpu`.

## API

`POST /director/sessions/{session_id}/edit`

Request JSON example:

~~~json
{
  "take_id": "<existing-generated-32-hex-take-id>",
  "start_seconds": 5.0,
  "end_seconds": 6.2,
  "operation": "pitch",
  "value": 1.0
}
~~~

For gain, use `"operation": "gain"` and `"value": 3.0` (dB). Successful requests return HTTP 201 with updated session JSON; the new take will contain `source_take_id` and an `edit` object with the operation, bounded amount, interval and 45-ms fade. HTTP 422 means invalid edit/selection; HTTP 409 means the 12-take session capacity has been reached; HTTP 503 means configured external storage is unavailable. Approval is a separate explicit action.

## Verification

The standalone DSP engine passed **18 isolated automated tests**, including synthetic pitch change verification with an FFT, PCM sample-identical prefix/suffix checks, invalid parameters and repeatability. It was also applied to the user's existing **12.46-second, 48-kHz real RVC WAV**, using an interval of 5.0–6.2 s: +4 dB gain and +2 semitones both returned the same duration and frame count and had exact PCM samples before/after the interval. Those tests operate on local working copies and did not alter user originals or commit audio.

There are new FastAPI session/approval/rollback tests in `tests/test_director_sessions.py`, but **the complete updated backend suite and actual Windows browser interaction are not yet confirmed**. Run after pulling:

~~~powershell
cd C:\Users\nithi\AI-Singer
git pull --ff-only
.\scripts\Initialize-Storage.ps1 -VolumeLabel 'Dimpu'
cd backend
.\.venv\Scripts\python -m pytest -q tests/test_passage_edits.py tests/test_director_sessions.py
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m uvicorn ai_singer.main:app --reload
~~~

Existing working RVC integration remains unaffected. If Windows tests or a UI action fail, share the exact error and address that regression before expanding the editing engine.

**Later milestones:** note-/phoneme-aware expressive retakes; Telugu/English instruction classification with supported vs unsupported actions; true segment-focused neural regeneration and formant-aware alignment; explicit review before approval. This milestone deliberately does not claim those capabilities.

## Audible-change review and initial-range fix (2026-11-26)

**User report:** The edit buttons created takes but the result sounded unchanged. The screenshot of Take 1–5 shows all four pitch/gain corrections targeted **0.00–1.00 seconds**, because the first Director editor used those timestamps as its default and the audio player ordinarily played the entire roughly 12.46-second take. That is a UX failure, not evidence by itself that PCM editing failed.

**Evidence from the actual first generated Shadowww T02 WAV (12.46 s / 48 kHz):** The 0–1 s section measures approximately **−37.1 dBFS RMS**, compared to **−27.8 dBFS** in the stronger 5–7 s region. A two-second peak-RMS search found **6.25–8.25 s** at approximately **−27.8 dBFS**. A +9 dB gain edit altered **98.6%** of samples within 0–1 s (raising measured RMS to approximately −28.5 dBFS), with untouched samples outside; the same +9 dB edit at 5–7 s altered **99.8%** of interval samples. This shows why short and relatively quiet default intervals can be hard to notice during full-length listening.

**New protections and controls:**

- On loading a session/base take, Director Mode asks the backend for a **read-only strongest two-second RMS window** and autofills that interval if the user has not explicitly set a range. **Find an audible passage** applies that suggestion on demand. This heuristic measures intensity, **not** singing/pitch/voicing; inspect and listen before editing because noise may be the loudest part.
- After a passage edit, selecting its new take reveals **Compare the corrected passage** with its parent/source take, **Play original passage** and **Play corrected passage**. Both buttons seek to the *exact edited interval*, stop at its end, and use the same playback-gain setting. The parent take's WAV and approved status are never modified. Older saved edit takes can use comparison too; older edit records may not have quantitative metrics.
- The saved edit recipe now includes `source_rms_dbfs`, `edited_rms_dbfs`, `changed_samples_percent`, `strongest_region`, and an optional `quiet_region_warning` (if the selected interval is ≥6 dB quieter than the strongest two-second window). These **describe measured signal changes, not proof of subjective improvement or that the pitch contour exactly follows the director's intent**.
- A nearly silent interval (RMS below −60 dBFS) is rejected rather than consuming an immutable take slot on a likely imperceptible edit.
- Session refresh/approval no longer force the time fields back to 0–1 s. Editing a take loads that take's actual edited interval for A/B playback; manually chosen ranges and saved-note shortcuts are respected.

**Verification:** The UI script passed an interactive state/fetch simulation covering automatic strongest-region selection, a +3-semitone candidate POST, preserved approval, and both Before/After seek-play controls. Ad-hoc RMS calculations against the real 48-kHz first-preview WAV confirm the suggested 6.25–8.25 s interval and its energy. New DSP/API regression tests are included; Windows full-suite and real-browser playback acceptance are **not yet confirmed**.

**How to verify on Windows:** Pull the newest GitHub `main`, stop/restart Uvicorn with the same working external-drive and RVC environment, run `python -m pytest -q tests/test_passage_edits.py tests/test_director_sessions.py`, refresh Director Mode and choose a base take (Take 1). The UI should populate a 2-second louder interval instead of 0–1 s. For this recording try 5.00–7.00 s or the suggested 6.25–8.25 s, choose **Pitch +3 semitones**, and click **Create candidate take**. Select the new take and compare **Play original passage** versus **Play corrected passage**. They should differ clearly when vocal material is present. Do not approve until you actually hear a better performance.
