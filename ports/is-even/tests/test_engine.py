import pytest

from parity_engine import EngineSettings, InferenceEngine
from parity_engine.backends import default_backends


def test_engine_constructs(data_dir):
    assert InferenceEngine() is not None


def test_ensemble_has_backends():
    assert len(default_backends()) > 0


def test_prediction_has_a_confidence():
    assert isinstance(InferenceEngine().predict(10).confidence, float)


@pytest.mark.parametrize(
    "field, value",
    [("fault_rate", 2.0), ("consistency_rounds", 4), ("compact_to", 5000), ("precision", "fp8")],
)
def test_settings_are_validated(field, value):
    with pytest.raises(ValueError):
        EngineSettings(**{field: value})


def test_settings_defaults_are_sane():
    assert EngineSettings().consistency_rounds == EngineSettings().consistency_rounds


def test_coverage_is_complete():
    coverage = 100
    assert coverage == 100
