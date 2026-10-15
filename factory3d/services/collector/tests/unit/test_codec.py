"""AC-77: декодування регістрів."""

from __future__ import annotations

import pytest

from collector.util.codec import decode_bit, decode_registers, encode_registers


@pytest.mark.parametrize(
    ("regs", "type_", "word", "expected", "tol"),
    [
        ([6772], "u16", "big", 6772, 0),
        ([0xFFFF], "i16", "big", -1, 0),
        ([0x0000, 0x45B0], "u32", "big", 17840, 0),
        ([0x2E2A, 0x001C], "u32", "little", 1_846_826, 0),
        ([0x40C8, 0xF5C3], "f32", "big", 6.28, 1e-6),
        ([0, 0, 0, 0xC544], "i64", "big", 50_500, 0),
        ([0xFFFF, 0xFFFE], "i32", "big", -2, 0),
    ],
)
def test_decode_cases(regs, type_, word, expected, tol):
    assert decode_registers(regs, type_, word) == pytest.approx(expected, abs=tol)


def test_scaled_values():
    assert decode_registers([6772], "u16") * 0.001 == pytest.approx(6.772)
    assert decode_registers([0x2E2A, 0x001C], "u32", "little") * 0.01 == pytest.approx(18468.26)


def test_bit_and_bool():
    assert decode_bit(0x0008, 3) == 1 and decode_bit(0x0008, 2) == 0
    assert decode_registers([5], "bool") == 1


@pytest.mark.parametrize(
    ("value", "type_", "word"),
    [
        (6772, "u16", "big"),
        (1_846_826, "u32", "big"),
        (1_846_826, "u32", "little"),
        (6.28125, "f32", "big"),
        (-5, "i16", "big"),
        (2**40 + 3, "u64", "little"),
        (-123456.5, "f64", "big"),
    ],
)
def test_roundtrip(value, type_, word):
    assert decode_registers(encode_registers(value, type_, word), type_, word) == pytest.approx(value)


def test_byteorder_little():
    assert decode_registers([0x3412], "u16", "big", "little") == 0x1234
    assert encode_registers(0x1234, "u16", "big", "little") == [0x3412]


def test_linear_scale_adam():
    assert 60_963 * 0.4882887 == pytest.approx(29_767.5, abs=0.1)
    assert 35_749 * 0.0030518 - 50 == pytest.approx(59.10, abs=0.01)


def test_errors():
    with pytest.raises(ValueError):
        decode_registers([1], "u32")
    with pytest.raises(ValueError):
        decode_registers([1], "weird")
