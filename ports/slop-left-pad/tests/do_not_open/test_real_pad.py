"""The real tests. Sleeps are pinned so they are fast."""
import pandas as pd
import pytest

import slop_left_pad as slp


@pytest.fixture
def npm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep registry.xlsx out of the repo
    monkeypatch.setattr(slp.time, "sleep", lambda seconds: None)
    return monkeypatch


@pytest.mark.parametrize("value, length, ch, expected", [
    ("5", 3, "0", "005"),
    ("abc", 2, " ", "abc"),
    ("abc", 3, " ", "abc"),
    ("", 2, "-", "--"),
    (42, 5, "0", "00042"),
    ("x", "4", "*", "***x"),
    ("x", 3.9, ".", "..x"),
    ("x", -3, "0", "x"),
    ("x", "banana", "0", "x"),
])
def test_happy_path(npm, value, length, ch, expected):
    assert slp.left_pad(value, length, ch) == expected


def test_default_pad_char_is_space(npm):
    assert slp.left_pad("x", 3) == "  x"


def test_only_first_pad_character_is_used(npm):
    assert slp.left_pad("x", 4, "ab") == "aaax"
    assert slp.left_pad("x", 3, "") == "  x"


def test_none_is_undefined_and_none_pad_is_N(npm):
    assert slp.left_pad(None, 11) == "  undefined"
    assert slp.left_pad("x", 3, None) == "NNx"


def test_length_is_capped_at_254(npm):
    assert len(slp.left_pad("x", 1000, "0")) == 254


def test_long_strings_are_untouched_by_the_cap(npm):
    assert slp.left_pad("x" * 300, 1000) == "x" * 300


def test_every_11th_call_unpublishes_then_comes_back(npm):
    for _ in range(10):
        assert slp.left_pad("5", 3, "0") == "005"
    with pytest.raises(slp.PackageUnpublishedError, match="404"):
        slp.left_pad("5", 3, "0")
    assert slp.left_pad("5", 3, "0") == "005"  # republished
    for _ in range(9):
        slp.left_pad("5", 3, "0")
    with pytest.raises(slp.PackageUnpublishedError):
        slp.left_pad("5", 3, "0")  # 22nd call


def test_every_call_is_a_row_in_the_registry(npm):
    slp.left_pad("a", 2)
    slp.left_pad("b", 2)
    registry = pd.read_excel(slp.REGISTRY_FILE)
    assert registry["published"].tolist() == [True, True]


def test_broken_registry_republishes_the_package(npm, tmp_path):
    for _ in range(10):
        slp.left_pad("a", 2)
    (tmp_path / slp.REGISTRY_FILE).write_text("not an excel file")
    assert slp.left_pad("a", 2) == " a"  # would have been the 11th call


def test_open_in_excel_still_pads(npm):
    npm.setattr(pd.DataFrame, "to_excel", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError()))
    assert slp.left_pad("7", 2, "0") == "07"  # logged (probably)
