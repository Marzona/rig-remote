import pytest

from rig_remote.rig_backends.mode_translator import (
    ModeTranslator,
    _GQRX_TO_HAMLIB,
    _HAMLIB_TO_GQRX,
)
from rig_remote.rig_backends.protocol import BackendType


@pytest.mark.parametrize(
    "mode",
    ["AM", "FM", "WFM", "USB", "LSB", "CW", "RTTY", "SomeUnknownMode"],
)
def test_to_backend_gqrx_passthrough(mode):
    translator = ModeTranslator(BackendType.GQRX)
    assert translator.to_backend(mode) == mode


@pytest.mark.parametrize(
    "value",
    ["AM", "FM", 42, 0, "anything"],
)
def test_from_backend_gqrx_passthrough(value):
    translator = ModeTranslator(BackendType.GQRX)
    assert translator.from_backend(value) == str(value)


@pytest.mark.parametrize(
    "mode, expected",
    list(_GQRX_TO_HAMLIB.items()),
)
def test_to_backend_hamlib_mapped_modes(mode, expected):
    translator = ModeTranslator(BackendType.HAMLIB)
    assert translator.to_backend(mode) == expected


def test_to_backend_hamlib_sb_raises():
    translator = ModeTranslator(BackendType.HAMLIB)
    with pytest.raises(ValueError):
        translator.to_backend("SB")


def test_to_backend_hamlib_unknown_raises():
    translator = ModeTranslator(BackendType.HAMLIB)
    with pytest.raises(ValueError):
        translator.to_backend("TOTALLY_UNKNOWN_MODE")


@pytest.mark.parametrize(
    "hamlib_int, expected_str",
    list(_HAMLIB_TO_GQRX.items()),
)
def test_from_backend_hamlib_mapped_constants(hamlib_int, expected_str):
    translator = ModeTranslator(BackendType.HAMLIB)
    assert translator.from_backend(hamlib_int) == expected_str


def test_from_backend_hamlib_unknown_raises():
    translator = ModeTranslator(BackendType.HAMLIB)
    with pytest.raises(ValueError):
        translator.from_backend(999999)
