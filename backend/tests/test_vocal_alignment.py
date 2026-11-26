"""Synthetic alignment fixtures; not evidence of human singing accuracy."""
import json
import pytest

from ai_singer.vocal_alignment import align_performances


def phrase(notes, *, hop=.02, leading=0, trailing=0, shift=0, octave=False):
    values = [None] * round(leading / hop)
    for pitch, duration in notes:
        values.extend([None if pitch is None else pitch + shift] * round(duration / hop))
    values.extend([None] * round(trailing / hop))
    # Match the analysis API convention: timestamps are measured sample positions.
    frames = [{"time_seconds": round(i * hop, 3), "midi_note": p,
               "rms": .001 if p is None else .1} for i, p in enumerate(values)]
    return {"pitch_track": frames, "duration_seconds": round(len(frames) * hop, 3),
            "octave_jump_candidates": [{"review": True}] if octave else []}


def test_register_and_edge_silence_are_not_pitch_corrections():
    notes = [(60, .6), (64, .8), (62, .6)]
    a = align_performances(phrase(notes), phrase(notes, leading=.8, trailing=.2, shift=-12))
    assert a["status"] == "reviewable_alignment"
    assert a["metrics"]["register_difference_semitones"] == -12
    assert a["metrics"]["aligned_median_difference_cents"] == 0
    assert a["metrics"]["minimum_voiced_coverage"] == 1
    assert a["demo_edges"]["leading_quiet_seconds"] == .8
    assert a["demo_edges"]["trailing_quiet_seconds"] == pytest.approx(.2)
    assert not a["review_regions"]
    assert "review_leading_quiet" in {p["action"] for p in a["timing_review"]}
    assert all(not p["executable"] for p in a["timing_review"])
    json.dumps(a, allow_nan=False)


def test_local_alignment_preserves_order_and_each_point_once():
    notes = [(60, .6), (64, .8), (62, .6)]
    different_timing = [(60, .8), (64, .6), (62, .6)]
    a = align_performances(phrase(notes), phrase(different_timing, leading=.4))
    assert a["metrics"]["unmatched_target_points"] > 0
    assert a["metrics"]["unmatched_demo_points"] > 0
    assert a["metrics"]["aligned_p90_difference_cents"] <= 200
    for side in ("target", "demo"):
        ts = [r[side]["time_seconds"] for r in a["path"] if r[side] is not None]
        assert len(ts) == 101
        assert ts == sorted(ts)
    target_i = demo_i = 0
    for row in a["path"]:
        target_i += row["target"] is not None
        demo_i += row["demo"] is not None
        assert abs(target_i - demo_i) <= a["band_points"]


def test_internal_pause_not_trimmed_or_hidden():
    a = align_performances(phrase([(60, .7), (None, .6), (64, .7)]),
                           phrase([(60, .7), (62, .6), (64, .7)]))
    assert a["target_edges"]["leading_quiet_seconds"] == 0
    assert any(r["target"] is not None and r["target"]["absolute_midi"] is None
               for r in a["path"])
    assert (a["metrics"]["unmatched_target_points"] or
            a["metrics"]["voicing_mismatch_matches"])
    assert all(not p["executable"] for p in a["timing_review"])


def test_opposite_melody_cannot_be_force_matched():
    a = align_performances(phrase([(55, .7), (60, .7), (67, .7)]),
                           phrase([(67, .7), (60, .7), (55, .7)]))
    assert a["status"] == "uncertain_alignment"
    assert a["review_regions"] == []


def test_missing_voicing_and_octave_candidates_block_proposals():
    sung = phrase([(60, 1), (64, 1)])
    quiet = align_performances(sung, phrase([(None, 2)]))
    assert quiet["status"] == "insufficient_evidence"
    assert quiet["metrics"] is None
    assert quiet["review_regions"] == []
    flagged = align_performances(sung, phrase([(60, 1), (64, 1)], octave=True))
    assert flagged["status"] == "uncertain_alignment"
    assert flagged["review_regions"] == []


def test_sustained_relative_difference_proposes_review_only():
    # Symmetric unchanged tones preserve the median register while a middle
    # region differs by one semitone.
    notes = [(60, .7), (62, .7), (64, .7), (62, .7), (60, .7)]
    changed = [(60, .7), (62, .7), (65, .7), (62, .7), (60, .7)]
    a = align_performances(phrase(notes), phrase(changed))
    assert a["status"] == "reviewable_alignment"
    assert any(p["action"] == "review_possible_fixed_pitch_shift"
               and p["median_relative_difference_semitones"] == 1
               for p in a["review_regions"])
    assert all(not p["executable"] for p in a["review_regions"])
