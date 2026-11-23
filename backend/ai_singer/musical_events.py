"""Candidate stable notes, pitch transitions, and suspicious octave excursions.

Pitch tracks are observations, not scores. Raw measurements are never rewritten.
"""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import median_filter

MIN_NOTE_FRAMES = 6
MIN_TRANSITION_FRAMES = 5
OCTAVE_TOLERANCE = 1.5
STABLE_LOCAL_RANGE = 0.65  # semitones within the short window
STABLE_TREND_CHANGE = 0.5  # maximum median drift across a longer window
TREND_RADIUS_SECONDS = 0.24


@dataclass(frozen=True)
class MelodicEvents:
    notes: list[dict]
    transitions: list[dict]
    octave_candidates: list[dict]


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def detect_octave_candidates(
    midi: np.ndarray, step: float, duration: float
) -> tuple[list[dict], np.ndarray]:
    """Flag a short octave-like jump only if nearby pitch returns."""
    observed = np.asarray(midi, dtype=float)
    grouping = observed.copy()
    flagged: list[dict] = []
    n = len(observed)
    i = 2
    while i < n - 1:
        before = observed[max(0, i - 4):i]
        before = before[np.isfinite(before)]
        if len(before) < 2 or not np.isfinite(observed[i]):
            i += 1
            continue
        reference = float(np.median(before))
        jump = float(observed[i] - reference)
        if abs(abs(jump) - 12) > OCTAVE_TOLERANCE:
            i += 1
            continue

        found = False
        for stop in range(i + 1, min(n, i + 11)):
            trailing = observed[stop]
            if np.isfinite(trailing) and abs(trailing - reference) <= 2.5:
                passage = observed[i:stop]
                valid = passage[np.isfinite(passage)]
                if (1 <= len(valid) <= 4 and
                    np.all(np.abs((valid - reference) - jump) <= 1.5)):
                    flagged.append({
                        "start_seconds": round(i * step, 3),
                        "end_seconds": round(min(stop * step, duration), 3),
                        "deviation_semitones": round(float(np.median(valid - reference)), 2),
                        "reason": "brief_octave_like_excursion",
                        "status": "needs_review",
                    })
                    grouping[i:stop] = np.nan
                    i = stop
                    found = True
                break
            if np.isfinite(trailing) and abs((trailing - reference) - jump) > 1.5:
                break
        if not found:
            i += 1
    return flagged, grouping


def segment_pitch(midi: np.ndarray, step: float, duration: float) -> MelodicEvents:
    """Return plateau cores and movement rather than quantizing every glide."""
    observed = np.asarray(midi, dtype=float)
    if observed.ndim != 1 or step <= 0 or duration <= 0:
        raise ValueError("Expected a pitch sequence and positive timing values.")
    octave_candidates, grouping = detect_octave_candidates(observed, step, duration)
    n = len(grouping)
    smoothed = grouping.copy()
    for begin, end in _runs(np.isfinite(grouping)):
        smoothed[begin:end] = median_filter(grouping[begin:end], size=5, mode="nearest")

    stable = np.zeros(n, dtype=bool)
    radius = 4  # 180 ms local window on the usual 20 ms grid.
    trend_radius = max(radius + 1, round(TREND_RADIUS_SECONDS / step))
    for begin, end in _runs(np.isfinite(smoothed)):
        for j in range(begin, end):
            left, right = max(begin, j - radius), min(end, j + radius + 1)
            window = smoothed[left:right]
            if len(window) < 5 or np.ptp(window) > STABLE_LOCAL_RANGE:
                continue

            # Slow glides look flat within 180 ms. Median pitches at the
            # ends of a longer interval reveal drift but tolerate vibrato.
            trend = smoothed[max(begin, j - trend_radius):min(end, j + trend_radius + 1)]
            count = max(2, len(trend) // 3)
            drift = abs(float(np.median(trend[-count:]) - np.median(trend[:count])))
            if drift <= STABLE_TREND_CHANGE:
                stable[j] = True

    stable_cores: list[tuple[int, int, int]] = []
    for start, stop in _runs(stable):
        if stop - start >= MIN_NOTE_FRAMES:
            stable_cores.append((start, stop, int(np.rint(np.median(smoothed[start:stop])))))

    merged: list[tuple[int, int, int]] = []
    for start, stop, note in stable_cores:
        if merged and note == merged[-1][2] and start - merged[-1][1] <= 4:
            old_start, _, old_note = merged.pop()
            merged.append((old_start, stop, old_note))
        else:
            merged.append((start, stop, note))

    notes = [{
        "start_seconds": round(start * step, 3),
        "end_seconds": round(min(stop * step, duration), 3),
        "midi_note": note,
        "frequency_hz": round(float(440 * 2 ** ((note - 69) / 12)), 2),
        "classification": "stable_pitch_core",
        "note_boundary_status": "approximate",
    } for start, stop, note in merged]

    covered = np.zeros(n, dtype=bool)
    for start, stop, _ in merged:
        covered[start:stop] = True
    transitions = []
    for start, stop in _runs(np.isfinite(grouping) & ~covered):
        if stop - start < MIN_TRANSITION_FRAMES:
            continue
        movement = float(grouping[stop - 1] - grouping[start])
        transitions.append({
            "start_seconds": round(start * step, 3),
            "end_seconds": round(min(stop * step, duration), 3),
            "pitch_change_semitones": round(movement, 2),
            "classification": "glide_candidate" if abs(movement) >= 0.7 else "unstable_pitch",
            "status": "needs_review",
        })
    return MelodicEvents(notes, transitions, octave_candidates)
