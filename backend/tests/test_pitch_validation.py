"""Reference-labeled frame accuracy cannot be inferred from model agreement."""

import pytest

from ai_singer.pitch_validation import score_pitch, validate_reference


def sample(notes):
    return {"estimator":"rmvpe","duration_seconds":.12,
            "pitch_track":[{"time_seconds":round(i*.02,3),"midi_note":n} for i,n in enumerate(notes)]}


def test_ground_truth_errors_and_voicing():
    reference={"segments":[
        {"start_seconds":0,"end_seconds":.08,"midi_note":57},
        {"start_seconds":.08,"end_seconds":.12,"midi_note":None},
    ]}
    score=score_pitch(sample([57,57.25,None,69,None,57]),reference)
    assert score["labeled_pitch_frames"]==4
    assert score["labeled_quiet_frames"]==2
    assert score["missed_voiced_frames"]==1
    assert score["voiced_on_annotated_quiet_frames"]==1
    assert score["octave_error_frames"]==1
    assert score["median_absolute_pitch_error_cents"]==25


def test_unannotated_frames_do_not_affect_accuracy():
    reference={"segments":[{"start_seconds":.04,"end_seconds":.08,"midi_note":57}]}
    score=score_pitch(sample([90,90,57,57,90,90]),reference)
    assert score["labeled_pitch_frames"]==2
    assert score["median_absolute_pitch_error_cents"]==0


def test_only_annotated_silence_has_null_pitch_error():
    reference={"segments":[{"start_seconds":0,"end_seconds":.12,"midi_note":None}]}
    score=score_pitch(sample([None]*6),reference)
    assert score["median_absolute_pitch_error_cents"] is None
    assert score["voiced_on_annotated_quiet_frames"]==0


@pytest.mark.parametrize("segments",[
    [],
    [{"start_seconds":0,"end_seconds":.2,"midi_note":57}],
    [{"start_seconds":0,"end_seconds":.08,"midi_note":57},
     {"start_seconds":.06,"end_seconds":.1,"midi_note":60}],
    [{"start_seconds":.03,"end_seconds":.02,"midi_note":57}],
    [{"start_seconds":0,"end_seconds":.1,"midi_note":999}],
    [{"start_seconds":0,"end_seconds":.1,"midi_note":"57"}],
    [{"start_seconds":0,"end_seconds":.1,"midi_note":float("nan")}],
],ids=["empty","out-of-bounds","overlap","inverted","out-of-range","string","nonfinite"])
def test_bad_reference_rejected(segments):
    with pytest.raises(ValueError):
        validate_reference({"segments":segments},.12)
