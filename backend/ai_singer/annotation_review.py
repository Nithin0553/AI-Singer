"""Review manually marked note/rest windows and glide direction.
Labels are user judgments, not independently proven performance ground truth.
"""
from math import isfinite
import numpy as np
from ai_singer.pitch_validation import score_pitch, validate_reference


def validate_annotations(reference: dict, duration: float) -> None:
    if not isinstance(reference, dict):
        raise ValueError("Reference must be a JSON object.")
    segments = validate_reference(reference, duration)
    glides = reference.get("glides", [])
    if not isinstance(glides, list) or len(glides) > 100:
        raise ValueError("glides must be a list of at most 100 intervals.")
    intervals = [(p["start_seconds"], p["end_seconds"]) for p in segments]
    for g in glides:
        if not isinstance(g, dict):
            raise ValueError("Each glide must be an object.")
        start, end = g.get("start_seconds"), g.get("end_seconds")
        if (isinstance(start, bool) or isinstance(end, bool)
            or not isinstance(start, (int, float)) or not isinstance(end, (int, float))
            or not isfinite(start) or not isfinite(end)
            or start < 0 or end <= start or end > duration + 1e-6):
            raise ValueError("Glide intervals need valid start/end times within the recording.")
        if g.get("direction") not in ("up", "down", "unknown"):
            raise ValueError("Glide direction must be up, down or unknown.")
        intervals.append((start, end))
    if len(intervals) > 200:
        raise ValueError("Too many labeled intervals (maximum 200).")
    intervals.sort()
    if any(start < last_end - 1e-8 for (_, last_end), (start, _) in zip(intervals, intervals[1:])):
        raise ValueError("Notes, rests and glides must not overlap.")


def _glide_reviews(track: dict, glides: list[dict]) -> list[dict]:
    frames = track["pitch_track"]
    times = np.asarray([f["time_seconds"] for f in frames], dtype=float)
    pitches = np.asarray([np.nan if f["midi_note"] is None else f["midi_note"]
                          for f in frames], dtype=float)
    reviews = []
    for g in glides:
        start, end = float(g["start_seconds"]), float(g["end_seconds"])
        inside = (times >= start) & (times < end)
        voiced = inside & np.isfinite(pitches)
        edge = min(.20, (end - start) / 2)
        beginning = pitches[voiced & (times < start + edge)]
        ending = pitches[voiced & (times >= end - edge)]
        change, observed = None, "insufficient_voicing"
        if len(beginning) >= 2 and len(ending) >= 2:
            change = round(float(np.median(ending) - np.median(beginning)), 2)
            observed = "up" if change >= .5 else "down" if change <= -.5 else "flat_or_uncertain"
        direction = g["direction"]
        agrees = None if direction == "unknown" or observed == "insufficient_voicing" else observed == direction
        reviews.append({
            "start_seconds": start, "end_seconds": end,
            "annotated_direction": direction, "observed_direction": observed,
            "observed_pitch_change_semitones": change,
            "voiced_frames": int(np.count_nonzero(voiced)),
            "frame_count": int(np.count_nonzero(inside)),
            "direction_agrees": agrees,
        })
    return reviews


def score_annotations(analysis: dict, reference: dict) -> dict:
    """Score existing note/rest reference; glide direction remains a review aid."""
    if not isinstance(analysis, dict):
        raise ValueError("analysis must be a comparison/analyzer JSON object.")
    tracks = {name: analysis[name] for name in ("yin", "rmvpe") if isinstance(analysis.get(name), dict)}
    if not tracks and "pitch_track" in analysis and analysis.get("estimator") in ("yin", "rmvpe"):
        tracks = {analysis["estimator"]: analysis}
    if not tracks:
        raise ValueError("Analysis must contain a YIN or RMVPE pitch track.")
    duration = float(analysis.get("duration_seconds", next(iter(tracks.values()))["duration_seconds"]))
    if not isfinite(duration) or duration <= 0 or duration > 15.01:
        raise ValueError("Invalid analysis duration.")
    validate_annotations(reference, duration)
    for name, track in tracks.items():
        if abs(float(track["duration_seconds"]) - duration) > .025:
            raise ValueError(f"{name} duration does not match the recording.")
        if len(track.get("pitch_track", [])) > 1000:
            raise ValueError("Pitch track exceeds the short-clip frame limit.")
    return {
        "annotation_source": "manual_unverified",
        "scoring_scope": "Held-note and rest intervals only; glides reviewed separately.",
        "scores": {name: {
            **score_pitch(track, reference),
            "glide_reviews": _glide_reviews(track, reference.get("glides", [])),
        } for name, track in tracks.items()},
    }
