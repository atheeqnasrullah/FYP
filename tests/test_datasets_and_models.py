import numpy as np
import pandas as pd
import pytest
from src.data.public_datasets import FS, GESTURES, load_source, segment_ids
from src.features.build_dataset import build
from src.features.emg_features import FEATURES
from src.models.train_emg import subject_normalise, within_subject_split
from src.utils.config import runtime_labels


@pytest.mark.parametrize("source,subjects", [("healthy", 9), ("stroke_patient", 1)])
def test_sources_load_all_gestures(source, subjects):
    data = load_source(source)
    assert data.subject_id.nunique() == subjects
    assert sorted(data.label.unique()) == sorted(GESTURES)
    assert data.emg_value.notna().all() and data.emg_value.between(0, 4095).all()
    assert set(data.signal_type) == {"envelope"} and set(data.fs) == {FS}


def test_gestures_match_runtime_labels():
    assert sorted(GESTURES) == sorted(runtime_labels())


def test_stroke_patient_is_kept_separate():
    data = load_source("stroke_patient")
    assert set(data.cohort) == {"stroke_patient"} and data.subject_id.nunique() == 1
    assert not set(data.subject_id) & set(load_source("healthy").subject_id)


def test_segments_split_at_long_gaps_and_backward_steps():
    ts = [0, 10, 20, 120, 130, 2000, 2010, 1500, 1510]
    assert segment_ids(ts).tolist() == [0, 0, 0, 0, 0, 1, 1, 2, 2]


def test_build_public_features_uses_dataset_rate():
    features = build("stroke_patient")
    assert not features.empty and set(FEATURES) <= set(features.columns)
    assert features.groupby("trial_id").window_id.min().eq(0).all()
    # 60 s at 100 Hz with 200 ms windows every 100 ms -> 599 windows per movement
    assert features.groupby("label").size().eq(599).all()


def test_within_subject_split_leaves_gap():
    df = pd.DataFrame({"trial_id": ["a"] * 20, "window_id": range(20)})
    train, test = within_subject_split(df)
    assert train.sum() == 14 and test.any()
    assert df.window_id[test].min() - df.window_id[train].max() > 2


def test_subject_normalise_zero_mean():
    df = pd.DataFrame({"subject_id": ["s1"] * 4 + ["s2"] * 4, **{f: np.arange(8.0) * (i + 1) for i, f in enumerate(FEATURES)}})
    out = subject_normalise(df)
    assert np.allclose(out.groupby("subject_id")[FEATURES].mean(), 0)


def test_runtime_labels_match_games():
    assert runtime_labels() == ["Rest", "Hand_Open", "Hand_Close", "Left", "Right", "Up", "Down"]
