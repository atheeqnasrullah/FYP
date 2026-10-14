import numpy as np
import pandas as pd
import pytest
from src.data.public_datasets import GESTURES, SOURCES, load_source
from src.features.build_dataset import build
from src.features.emg_features import FEATURES
from src.models.train_emg import subject_normalise, within_subject_split
from src.utils.config import runtime_labels


@pytest.mark.parametrize("source,subjects", [("healthy_raw", 11), ("healthy_filtered", 11), ("simulated_patient", 3)])
def test_sources_load_all_gestures(source, subjects):
    data = load_source(source)
    assert data.subject_id.nunique() == subjects
    assert sorted(data.label.unique()) == sorted(GESTURES)
    assert data.emg_value.notna().all()
    assert set(data.signal_type) == {SOURCES[source]["signal_type"]}


def test_simulated_patients_are_kept_separate():
    data = load_source("simulated_patient")
    assert set(data.cohort) == {"simulated_patient"} and data.subject_id.str.startswith("SP").all()


def test_build_public_features():
    features = build("simulated_patient")
    assert not features.empty and set(FEATURES) <= set(features.columns)
    assert features.groupby("trial_id").window_id.min().eq(0).all()


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
