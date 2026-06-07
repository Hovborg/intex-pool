"""Unit tests for the pure decoders (no Home Assistant required)."""
import importlib.util
import pathlib

import pytest

# Import decode.py directly so these tests don't require the HA package.
_DECODE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "intex_pool" / "decode.py"
_spec = importlib.util.spec_from_file_location("intex_decode", _DECODE)
decode = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(decode)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0, "none"),
        (190, "e90"),
        (191, "e91"),
        (192, "e92"),
        (101, "e1"),
        (200, "end"),
        ("190", "e90"),  # tolerate string ints from Tuya
        (999, None),     # unknown code
        (None, None),
        ("garbage", None),
    ],
)
def test_normalize_error(raw, expected):
    assert decode.normalize_error(raw) == expected


def test_error_options_unique_and_complete():
    assert decode.ERROR_OPTIONS[0] == "none"
    assert "e90" in decode.ERROR_OPTIONS
    assert len(decode.ERROR_OPTIONS) == len(set(decode.ERROR_OPTIONS))


@pytest.mark.parametrize(
    "raw,expected",
    [("working", "working"), ("FP_mode", "fp_mode"), ("sleep", "sleep"),
     ("boost", "boost"), ("bogus", None), (None, None)],
)
def test_normalize_status(raw, expected):
    assert decode.normalize_status(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("normal", "normal"), ("E90", "e90"), ("E91E92", "e91e92"),
     ("E03E04", "e03e04"), ("weird", None), (None, None)],
)
def test_normalize_alarm(raw, expected):
    assert decode.normalize_alarm(raw) == expected


def test_normalize_indicator_uses_option_set():
    assert decode.normalize_indicator("green", decode.PH_INDICATOR_OPTIONS) == "green"
    assert decode.normalize_indicator("saltwater_abnormal", decode.ORP_INDICATOR_OPTIONS) == "saltwater_abnormal"
    # saltwater_abnormal is NOT valid for a plain pH indicator
    assert decode.normalize_indicator("saltwater_abnormal", decode.PH_INDICATOR_OPTIONS) is None
    assert decode.normalize_indicator("RED", decode.MAINTENANCE_OPTIONS) == "red"


@pytest.mark.parametrize(
    "raw,factor,expected",
    [(740, 0.01, 7.4), (780, 0.01, 7.8), (150, 0.01, 1.5),
     (0, 0.01, 0.0), (None, 0.01, None), ("740", 0.01, 7.4), ("x", 0.01, None)],
)
def test_scaled(raw, factor, expected):
    assert decode.scaled(raw, factor) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [(True, True), (False, False), (1, True), (0, False),
     ("true", True), ("ON", True), ("0", False), (None, None)],
)
def test_as_bool(raw, expected):
    assert decode.as_bool(raw) == expected
