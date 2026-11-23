"""Known-pitch synthetic tests for notes, glides, and octave anomalies."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from ai_singer.musical_events import detect_octave_candidates, segment_pitch
from ai_singer.pitch_benchmark import compare_results
from ai_singer.main import app
from test_audio_analysis import sine, wav_bytes

STEP = .02


def test_flat_note_is_one_core():
    events = segment_pitch(np.full(70, 57.), STEP, 1.4)
    assert len(events.notes) == 1
    assert events.notes[0]["midi_note"] == 57
    assert not events.transitions


def test_vibrato_is_not_many_notes():
    t = np.arange(80) * STEP
    events = segment_pitch(57 + .2 * np.sin(2 * np.pi * 5 * t), STEP, 1.6)
    assert len(events.notes) == 1


def test_continuous_glide_does_not_become_many_notes():
    events = segment_pitch(np.linspace(57, 63, 50), STEP, 1.0)
    assert not events.notes
    assert any(t["classification"] == "glide_candidate" for t in events.transitions)


def test_two_notes_separated_by_glide():
    pitch = np.r_[np.full(30, 57.), np.linspace(57, 62, 20), np.full(30, 62.)]
    events = segment_pitch(pitch, STEP, len(pitch) * STEP)
    assert [note["midi_note"] for note in events.notes] == [57, 62]


def test_short_octave_excursion_is_flagged_and_raw_pitch_unchanged():
    pitch = np.r_[np.full(25, 57.), np.full(3, 45.), np.full(25, 57.)]
    before = pitch.copy()
    events = segment_pitch(pitch, STEP, pitch.size * STEP)
    assert len(events.octave_candidates) == 1
    assert events.octave_candidates[0]["status"] == "needs_review"
    assert np.array_equal(pitch, before)
    assert [n["midi_note"] for n in events.notes] == [57]


def test_genuine_low_note_is_not_flagged():
    pitch = np.r_[np.full(25, 57.), np.full(25, 45.), np.full(25, 57.)]
    events = segment_pitch(pitch, STEP, pitch.size * STEP)
    assert not events.octave_candidates
    assert 45 in [n["midi_note"] for n in events.notes]


def test_octave_excursion_followed_by_unvoiced_gap():
    pitch = np.r_[np.full(25, 57.), np.full(3, 45.), np.full(4, np.nan), np.full(15, 58.)]
    errors, grouped = detect_octave_candidates(pitch, STEP, pitch.size * STEP)
    assert len(errors) == 1
    assert errors[0]["start_seconds"] == pytest.approx(.5)
    assert np.isnan(grouped[25])
    assert pitch[25] == 45


def test_unvoiced_has_no_notes():
    events = segment_pitch(np.full(70, np.nan), STEP, 1.4)
    assert events.notes == events.transitions == events.octave_candidates == []


def test_note_end_is_bounded():
    events = segment_pitch(np.full(30, 57.), STEP, .595)
    assert max(note["end_seconds"] for note in events.notes) <= .595


@pytest.mark.parametrize("midi,step,duration", [
    (np.array([[57.]]), STEP, 1.), (np.array([57.]), 0, 1.),
], ids=["multidimensional", "invalid-step"])
def test_invalid_input(midi, step, duration):
    with pytest.raises(ValueError):
        segment_pitch(midi, step, duration)


def test_compare_reports_octave_disagreement_interval():
    def report(notes):
        return {"pitch_track": [{"time_seconds": round(i*STEP,3), "midi_note": note}
                                for i,note in enumerate(notes)]}
    summary = compare_results(report([57,57,45,45,45,57,57]), report([57]*7))
    assert summary["octave_like_disagreement_frames"] == 3
    assert len(summary["disagreement_intervals"]) == 1
    assert summary["disagreement_intervals"][0]["classification"] == "octave_like"


def test_single_disagreeing_frame_is_not_a_span():
    def report(notes):
        return {"pitch_track": [{"time_seconds": i*STEP, "midi_note": note}
                                for i,note in enumerate(notes)]}
    assert not compare_results(report([57,57,57]),report([57,58.5,57]))["disagreement_intervals"]


def test_pitch_lab_page_served_without_external_assets():
    response = TestClient(app).get("/pitch-lab")
    assert response.status_code == 200
    assert "AI Singer" in response.text and "/compare" in response.text
    assert 'src="http' not in response.text


def test_compare_missing_model_returns_503(monkeypatch,tmp_path):
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT",str(tmp_path))
    monkeypatch.delenv("AI_SINGER_RMVPE_MODEL",raising=False)
    response=TestClient(app).post("/compare",files={"file":("a.wav",wav_bytes(sine(220,2)),"audio/wav")})
    assert response.status_code == 503


def test_compare_with_mock_model(monkeypatch,tmp_path):
    import ai_singer.rmvpe_pitch as module
    model=tmp_path/"rmvpe.onnx";model.write_bytes(b"mock only")
    monkeypatch.setenv("AI_SINGER_RMVPE_MODEL",str(model))
    class FakeModel:
        def predict(self,audio,sr):
            t=np.arange(201)*.01
            return t,np.full(len(t),220.),np.full(len(t),.95),None
    monkeypatch.setattr(module,"_load_model",lambda path:FakeModel())
    response=TestClient(app).post("/compare",files={"file":("a.wav",wav_bytes(sine(220,2)),"audio/wav")})
    assert response.status_code == 200,response.text
    result=response.json()
    assert result["agreement"]["overlapping_voiced_frames"]>50
    assert result["event_summary"]["yin_stable_pitch_cores"]>=1
    assert result["event_summary"]["rmvpe_stable_pitch_cores"]>=1


def test_compare_rejects_invalid_audio():
    response=TestClient(app).post("/compare",files={"file":("a.wav",b"bad","audio/wav")})
    assert response.status_code == 422
