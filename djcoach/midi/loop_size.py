"""Conversión del selector de tamaño de loop de Traktor."""

from __future__ import annotations

from fractions import Fraction


# Traktor distribuye las once opciones del selector uniformemente en MIDI 0-127.
# Los tamaños 4/8/16/32 y 1/2 fueron verificados físicamente con CC36/CC37.
LOOP_SIZE_MIDI_VALUES: tuple[tuple[int, Fraction], ...] = (
    (0, Fraction(1, 32)),
    (13, Fraction(1, 16)),
    (25, Fraction(1, 8)),
    (38, Fraction(1, 4)),
    (50, Fraction(1, 2)),
    (63, Fraction(1, 1)),
    (76, Fraction(2, 1)),
    (88, Fraction(4, 1)),
    (101, Fraction(8, 1)),
    (114, Fraction(16, 1)),
    (127, Fraction(32, 1)),
)


def loop_size_beats(midi_value: int | None) -> Fraction | None:
    """Devuelve la opción más cercana del selector para un MIDI 0-127."""
    if midi_value is None:
        return None
    _midi, beats = min(
        LOOP_SIZE_MIDI_VALUES,
        key=lambda option: abs(option[0] - int(midi_value)),
    )
    return beats


def _number(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def format_loop_size(midi_value: int | None, include_bars: bool = True) -> str:
    """Ej.: MIDI 101 -> '8 beats (2 compases)' en métrica 4/4."""
    beats = loop_size_beats(midi_value)
    if beats is None:
        return "---"
    beat_word = "beat" if beats <= 1 else "beats"
    result = f"{_number(beats)} {beat_word}"
    if include_bars and beats >= 4:
        bars = beats / 4
        bar_word = "compás" if bars == 1 else "compases"
        result += f" ({_number(bars)} {bar_word})"
    return result
