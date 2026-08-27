"""DJ Coach: monitor MIDI del mixer de Traktor."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

import mido

from djcoach.midi import format_loop_size, loop_size_beats


PORT_NAME_FRAGMENT = "djcoach"

DECK_A_CONTINUOUS_CONTROLS = {
    1: ("low", "LOW"),
    2: ("mid", "MID"),
    3: ("high", "HIGH"),
    4: ("gain", "GAIN"),
    5: ("fx_adjust", "FX/FILTER"),
    6: ("volume", "VOLUME"),
    28: ("phase", "PHASE"),
    30: ("beat_phase", "BEAT PHASE"),
    32: ("track_progress", "TRACK PROGRESS"),
    36: ("loop_size", "LOOP SIZE"),
}

DECK_A_BOOLEAN_CONTROLS = {
    7: ("fx_on", "FX"),
    8: ("cue", "CUE"),
    18: ("play", "PLAY"),
    20: ("loaded", "LOADED"),
    22: ("transport_cue", "CUE"),
    24: ("loop_active", "LOOP"),
    26: ("sync", "SYNC"),
    34: ("track_end_warning", "TRACK END"),
}

DECK_B_CONTINUOUS_CONTROLS = {
    9: ("low", "LOW"),
    10: ("mid", "MID"),
    11: ("high", "HIGH"),
    12: ("gain", "GAIN"),
    13: ("fx_adjust", "FX/FILTER"),
    17: ("volume", "VOLUME"),
    29: ("phase", "PHASE"),
    31: ("beat_phase", "BEAT PHASE"),
    33: ("track_progress", "TRACK PROGRESS"),
    37: ("loop_size", "LOOP SIZE"),
}

DECK_B_BOOLEAN_CONTROLS = {
    14: ("fx_on", "FX"),
    15: ("cue", "CUE"),
    19: ("play", "PLAY"),
    21: ("loaded", "LOADED"),
    23: ("transport_cue", "CUE"),
    25: ("loop_active", "LOOP"),
    27: ("sync", "SYNC"),
    35: ("track_end_warning", "TRACK END"),
}

CROSSFADER_CC = 16
CROSSFADER_WIDTH = 25
POLL_INTERVAL_SECONDS = 0.02
DASHBOARD_REFRESH_SECONDS = 0.05
TIMING_HISTORY_SAMPLE_SECONDS = 0.10
HIGH_FREQUENCY_CCS = {28, 29, 30, 31, 32, 33}

AUDIBLE_VOLUME_THRESHOLD = 0.05
CROSSFADER_EDGE_THRESHOLD = 0.05
BASS_HIGH_THRESHOLD = 0.80
BASS_LOW_THRESHOLD = 0.25
BASS_OVERLAP_HOLD_SECONDS = 1.5
BASS_GAP_HOLD_SECONDS = 1.5
BASS_WARNING_COOLDOWN_SECONDS = 8.0
TRANSITION_END_HOLD_SECONDS = 1.0
TRANSITION_TOO_FAST_SECONDS = 4.0
TRANSITION_TOO_SLOW_SECONDS = 45.0
PHASE_CENTER_MIDI = 63.5
PHASE_ERROR_THRESHOLD_MIDI = 12.0
PHASE_ERROR_HOLD_SECONDS = 1.0
PHASE_WARNING_COOLDOWN_SECONDS = 8.0
FADER_ABRUPT_WINDOW_SECONDS = 0.35
FADER_ABRUPT_DELTA = 0.45
FADER_WARNING_COOLDOWN_SECONDS = 5.0
WARNING_DISPLAY_SECONDS = 6.0
TRACK_END_WARNING_COOLDOWN_SECONDS = 15.0
SILENCE_RISK_HOLD_SECONDS = 0.75
SILENCE_WARNING_COOLDOWN_SECONDS = 8.0
MIDI_CLOCK_PULSES_PER_BEAT = 24
MIDI_CLOCK_WINDOW_PULSES = 384
MIDI_CLOCK_MIN_PULSES = 144
MIDI_CLOCK_ESTIMATE_WINDOW = 5
MIDI_CLOCK_SMOOTHING_ALPHA = 0.20
MIDI_CLOCK_STALE_SECONDS = 0.5
BEAT_PHASE_CC_BY_DECK = {30: "a", 31: "b"}
BEAT_PHASE_WRAP_HIGH = 90
BEAT_PHASE_WRAP_LOW = 35
DECK_BPM_STALE_SECONDS = 2.5
DECK_BPM_PHASE_WINDOW_SECONDS = 8.0
DECK_BPM_MIN_SAMPLE_SECONDS = 2.0
DECK_BPM_MIN_SAMPLES = 20
DECK_BPM_ESTIMATE_WINDOW = 5
DECK_BPM_SMOOTHING_ALPHA = 0.25

SESSION_DIRECTORY = Path(__file__).resolve().parent / "sessions"

DISPLAY_CONTROLS = (
    ("low", "LOW"),
    ("mid", "MID"),
    ("high", "HIGH"),
    ("gain", "GAIN"),
    ("fx_adjust", "FX/FILTER"),
    ("volume", "VOLUME"),
)

DISPLAY_TIMING_CONTROLS = (
    ("phase", "PHASE"),
    ("beat_phase", "BEAT PH"),
)


def enable_ansi_on_windows() -> bool:
    """Habilita secuencias ANSI en la consola clásica de Windows."""
    if os.name != "nt":
        return True

    stdout_handle = ctypes.windll.kernel32.GetStdHandle(-11)
    console_mode = ctypes.c_ulong()
    if not ctypes.windll.kernel32.GetConsoleMode(
        stdout_handle, ctypes.byref(console_mode)
    ):
        return False

    enable_virtual_terminal_processing = 0x0004
    return bool(
        ctypes.windll.kernel32.SetConsoleMode(
            stdout_handle,
            console_mode.value | enable_virtual_terminal_processing,
        )
    )


def find_djcoach_port(port_names: list[str]) -> str | None:
    """Devuelve el primer puerto MIDI cuyo nombre contiene 'djCoach'."""
    return next(
        (name for name in port_names if PORT_NAME_FRAGMENT in name.lower()),
        None,
    )


def iso_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def make_continuous_value(
    midi_value: int | None = None,
) -> dict[str, int | float | str | bool | None]:
    """Crea la representación MIDI, normalizada y porcentual de un control."""
    if midi_value is None:
        return {
            "midi": None,
            "normalized": None,
            "percentage": None,
            "received": False,
            "updated_at": None,
        }

    normalized = midi_value / 127
    return {
        "midi": midi_value,
        "normalized": normalized,
        "percentage": round(normalized * 100),
        "received": True,
        "updated_at": iso_timestamp(),
    }


def make_loop_size_value(midi_value: int | None = None) -> dict[str, Any]:
    """Crea el estado MIDI y musical del selector Loop Size de Traktor."""
    value = make_continuous_value(midi_value)
    beats = loop_size_beats(midi_value)
    value.update(
        {
            "beats": float(beats) if beats is not None else None,
            "label": format_loop_size(midi_value),
        }
    )
    return value


@dataclass(frozen=True)
class TimedMidiMessage:
    message: mido.Message
    received_at: float


def create_midi_clock_state() -> dict[str, Any]:
    return {
        "bpm": None,
        "received": False,
        "active": False,
        "tick_count": 0,
        "last_tick_at": None,
        "updated_at": None,
        "_tick_times": [],
        "_raw_estimates": [],
        "_smoothed_bpm": None,
    }


def update_midi_clock(
    midi_clock: dict[str, Any], message: mido.Message, received_at: float
) -> bool:
    """Calcula el BPM del Master Clock usando sus 24 pulsos MIDI por beat."""
    if message.type in {"start", "continue"}:
        midi_clock["active"] = True
        if message.type == "start":
            midi_clock["tick_count"] = 0
            midi_clock["_tick_times"] = []
            midi_clock["_raw_estimates"] = []
            midi_clock["_smoothed_bpm"] = None
        return True
    if message.type == "stop":
        changed = bool(midi_clock["active"])
        midi_clock["active"] = False
        midi_clock["_tick_times"] = []
        return changed
    if message.type != "clock":
        return False

    tick_times: list[float] = midi_clock["_tick_times"]
    tick_times.append(received_at)
    tick_times[:] = tick_times[-MIDI_CLOCK_WINDOW_PULSES:]
    midi_clock["received"] = True
    midi_clock["active"] = True
    midi_clock["tick_count"] += 1
    midi_clock["last_tick_at"] = received_at
    midi_clock["updated_at"] = iso_timestamp()

    previous_bpm = midi_clock["bpm"]
    should_estimate = (
        len(tick_times) >= MIDI_CLOCK_MIN_PULSES
        and midi_clock["tick_count"] % MIDI_CLOCK_PULSES_PER_BEAT == 0
    )
    if should_estimate:
        sample_count = len(tick_times)
        mean_index = (sample_count - 1) / 2
        mean_time = sum(tick_times) / sample_count
        covariance = sum(
            (index - mean_index) * (tick_at - mean_time)
            for index, tick_at in enumerate(tick_times)
        )
        variance = sum(
            (index - mean_index) ** 2 for index in range(sample_count)
        )
        seconds_per_pulse = covariance / variance if variance else 0.0
        if seconds_per_pulse > 0:
            raw_bpm = 60 / (
                seconds_per_pulse * MIDI_CLOCK_PULSES_PER_BEAT
            )
            estimates: list[float] = midi_clock["_raw_estimates"]
            estimates.append(raw_bpm)
            estimates[:] = estimates[-MIDI_CLOCK_ESTIMATE_WINDOW:]
            robust_bpm = median(estimates)
            smoothed_bpm = midi_clock["_smoothed_bpm"]
            if smoothed_bpm is None:
                smoothed_bpm = robust_bpm
            else:
                smoothed_bpm += MIDI_CLOCK_SMOOTHING_ALPHA * (
                    robust_bpm - smoothed_bpm
                )
            midi_clock["_smoothed_bpm"] = smoothed_bpm
            midi_clock["bpm"] = round(smoothed_bpm, 1)
    return previous_bpm != midi_clock["bpm"]


def refresh_midi_clock(midi_clock: dict[str, Any], now: float | None = None) -> bool:
    """Marca el reloj como detenido si dejaron de llegar pulsos."""
    now = time.monotonic() if now is None else now
    last_tick_at = midi_clock["last_tick_at"]
    if (
        midi_clock["active"]
        and last_tick_at is not None
        and now - float(last_tick_at) > MIDI_CLOCK_STALE_SECONDS
    ):
        midi_clock["active"] = False
        midi_clock["_tick_times"] = []
        midi_clock["_raw_estimates"] = []
        midi_clock["_smoothed_bpm"] = None
        return True
    return False


def create_deck_tempo_state() -> dict[str, Any]:
    return {
        "bpm": None,
        "received": False,
        "active": False,
        "beat_count": 0,
        "updated_at": None,
        "downbeat_set": False,
        "downbeat_armed": False,
        "beat_in_bar": None,
        "bar_count": None,
        "bar_in_block": {"4": None, "8": None, "16": None, "32": None},
        "block_count": {"4": None, "8": None, "16": None, "32": None},
        "_previous_value": None,
        "_last_beat_at": None,
        "_last_message_at": None,
        "_cycle_count": 0,
        "_phase_samples": [],
        "_bpm_estimates": [],
        "_smoothed_bpm": None,
        "_downbeat_beat_count": None,
    }


def create_deck_tempos_state() -> dict[str, dict[str, Any]]:
    return {"a": create_deck_tempo_state(), "b": create_deck_tempo_state()}


def update_deck_tempo_from_beat_phase(
    deck_tempos: dict[str, dict[str, Any]],
    message: mido.Message,
    received_at: float,
) -> bool:
    """Calcula el BPM individual detectando ciclos reales de Beat Phase."""
    if message.type != "control_change" or message.channel != 0:
        return False

    loaded_side = {20: "a", 21: "b"}.get(message.control)
    if loaded_side is not None:
        state = deck_tempos[loaded_side]
        reset_deck_tempo_analysis(state)
        reset_deck_rhythm(state)
        state["active"] = False
        state["beat_count"] = 0
        return True

    transport_side = {18: "a", 19: "b"}.get(message.control)
    if transport_side is not None and message.value == 0:
        state = deck_tempos[transport_side]
        was_active = bool(state["active"])
        state["active"] = False
        reset_deck_tempo_analysis(state)
        return was_active

    if message.control not in BEAT_PHASE_CC_BY_DECK:
        return False

    state = deck_tempos[BEAT_PHASE_CC_BY_DECK[message.control]]
    last_message_at = state["_last_message_at"]
    if (
        last_message_at is not None
        and received_at - float(last_message_at) > DECK_BPM_STALE_SECONDS
    ):
        reset_deck_tempo_analysis(state)
    state["_last_message_at"] = received_at
    previous_value = state["_previous_value"]
    state["_previous_value"] = message.value
    wrapped = (
        previous_value is not None
        and int(previous_value) >= BEAT_PHASE_WRAP_HIGH
        and message.value <= BEAT_PHASE_WRAP_LOW
    )
    state["active"] = True
    state["updated_at"] = iso_timestamp()
    if wrapped:
        state["_cycle_count"] += 1
        state["beat_count"] += 1
        state["_last_beat_at"] = received_at
        update_deck_rhythm_on_beat(state)

    unwrapped_phase = state["_cycle_count"] + message.value / 127
    samples: list[tuple[float, float]] = state["_phase_samples"]
    samples.append((received_at, unwrapped_phase))
    samples[:] = [
        sample
        for sample in samples
        if received_at - sample[0] <= DECK_BPM_PHASE_WINDOW_SECONDS
    ]

    enough_samples = (
        len(samples) >= DECK_BPM_MIN_SAMPLES
        and samples[-1][0] - samples[0][0] >= DECK_BPM_MIN_SAMPLE_SECONDS
    )
    if not wrapped or not enough_samples:
        return wrapped

    mean_time = sum(sample[0] for sample in samples) / len(samples)
    mean_phase = sum(sample[1] for sample in samples) / len(samples)
    covariance = sum(
        (sample_at - mean_time) * (phase - mean_phase)
        for sample_at, phase in samples
    )
    variance = sum((sample_at - mean_time) ** 2 for sample_at, _phase in samples)
    beats_per_second = covariance / variance if variance else 0.0
    raw_bpm = beats_per_second * 60
    if not 30 <= raw_bpm <= 300:
        return False

    estimates: list[float] = state["_bpm_estimates"]
    estimates.append(raw_bpm)
    estimates[:] = estimates[-DECK_BPM_ESTIMATE_WINDOW:]
    robust_bpm = median(estimates)
    smoothed_bpm = state["_smoothed_bpm"]
    if smoothed_bpm is None:
        smoothed_bpm = robust_bpm
    else:
        smoothed_bpm += DECK_BPM_SMOOTHING_ALPHA * (
            robust_bpm - smoothed_bpm
        )
    state["_smoothed_bpm"] = smoothed_bpm
    bpm = round(smoothed_bpm, 1)
    changed = bpm != state["bpm"] or not state["received"]
    state["bpm"] = bpm
    state["received"] = True
    return changed


def reset_deck_tempo_analysis(state: dict[str, Any]) -> None:
    state["_previous_value"] = None
    state["_last_beat_at"] = None
    state["_last_message_at"] = None
    state["_cycle_count"] = 0
    state["_phase_samples"] = []
    state["_bpm_estimates"] = []
    state["_smoothed_bpm"] = None


def reset_deck_rhythm(state: dict[str, Any]) -> None:
    state["downbeat_set"] = False
    state["downbeat_armed"] = False
    state["beat_in_bar"] = None
    state["bar_count"] = None
    state["bar_in_block"] = {"4": None, "8": None, "16": None, "32": None}
    state["block_count"] = {"4": None, "8": None, "16": None, "32": None}
    state["_downbeat_beat_count"] = None


def arm_deck_downbeat(
    deck_tempos: dict[str, dict[str, Any]], side: str
) -> None:
    """Prepara el próximo ciclo de Beat Phase como beat 1 del compás."""
    if side not in deck_tempos:
        raise ValueError("El deck debe ser 'a' o 'b'.")
    state = deck_tempos[side]
    reset_deck_rhythm(state)
    state["downbeat_armed"] = True


def update_deck_rhythm_on_beat(state: dict[str, Any]) -> None:
    if state["downbeat_armed"]:
        state["downbeat_armed"] = False
        state["downbeat_set"] = True
        state["_downbeat_beat_count"] = state["beat_count"]

    origin = state["_downbeat_beat_count"]
    if not state["downbeat_set"] or origin is None:
        return

    beats_since_downbeat = state["beat_count"] - int(origin)
    state["beat_in_bar"] = beats_since_downbeat % 4 + 1
    bar_count = beats_since_downbeat // 4 + 1
    state["bar_count"] = bar_count
    for block_size in (4, 8, 16, 32):
        key = str(block_size)
        state["bar_in_block"][key] = (bar_count - 1) % block_size + 1
        state["block_count"][key] = (bar_count - 1) // block_size + 1


def refresh_deck_tempos(
    deck_tempos: dict[str, dict[str, Any]], now: float | None = None
) -> bool:
    now = time.monotonic() if now is None else now
    changed = False
    for state in deck_tempos.values():
        last_beat_at = state["_last_beat_at"]
        if (
            state["active"]
            and last_beat_at is not None
            and now - float(last_beat_at) > DECK_BPM_STALE_SECONDS
        ):
            state["active"] = False
            reset_deck_tempo_analysis(state)
            changed = True
    return changed


def public_deck_tempos(
    deck_tempos: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        side: {
            key: value
            for key, value in state.items()
            if not key.startswith("_")
        }
        for side, state in deck_tempos.items()
    }


def effective_deck_bpm(
    deck: dict[str, Any],
    measured_tempo: dict[str, Any],
    midi_clock: dict[str, Any],
) -> tuple[float | None, str, bool]:
    """Elige Master Clock para Sync y Beat Phase para un deck independiente."""
    synced_to_master = (
        deck["sync_received"]
        and deck["sync"]
        and midi_clock["received"]
        and midi_clock["bpm"] is not None
    )
    if synced_to_master:
        return float(midi_clock["bpm"]), "SYNC / MASTER", bool(midi_clock["active"])
    if measured_tempo["received"]:
        return (
            float(measured_tempo["bpm"]),
            "BEAT PHASE",
            bool(measured_tempo["active"]),
        )
    return None, "SIN MEDIR", False


def create_deck_a_state() -> dict[str, Any]:
    """Crea el estado inicial de los controles mapeados del Deck A."""
    state: dict[str, Any] = {
        key: make_continuous_value()
        for key, _label in DECK_A_CONTINUOUS_CONTROLS.values()
    }
    state["loop_size"] = make_loop_size_value()
    state.update(
        {
            "fx_on": False,
            "fx_on_midi": None,
            "fx_on_received": False,
            "fx_on_updated_at": None,
            "cue": False,
            "cue_midi": None,
            "cue_received": False,
            "cue_updated_at": None,
            "play": False,
            "play_midi": None,
            "play_received": False,
            "play_updated_at": None,
            "loaded": False,
            "loaded_midi": None,
            "loaded_received": False,
            "loaded_updated_at": None,
            "transport_cue": False,
            "transport_cue_midi": None,
            "transport_cue_received": False,
            "transport_cue_updated_at": None,
            "loop_active": False,
            "loop_active_midi": None,
            "loop_active_received": False,
            "loop_active_updated_at": None,
            "sync": False,
            "sync_midi": None,
            "sync_received": False,
            "sync_updated_at": None,
            "track_end_warning": False,
            "track_end_warning_midi": None,
            "track_end_warning_received": False,
            "track_end_warning_updated_at": None,
        }
    )
    return state


def create_deck_b_state() -> dict[str, Any]:
    """Crea el estado inicial de los controles mapeados del Deck B."""
    state: dict[str, Any] = {
        key: make_continuous_value()
        for key, _label in DECK_B_CONTINUOUS_CONTROLS.values()
    }
    state["loop_size"] = make_loop_size_value()
    state.update(
        {
            "fx_on": False,
            "fx_on_midi": None,
            "fx_on_received": False,
            "fx_on_updated_at": None,
            "cue": False,
            "cue_midi": None,
            "cue_received": False,
            "cue_updated_at": None,
            "play": False,
            "play_midi": None,
            "play_received": False,
            "play_updated_at": None,
            "loaded": False,
            "loaded_midi": None,
            "loaded_received": False,
            "loaded_updated_at": None,
            "transport_cue": False,
            "transport_cue_midi": None,
            "transport_cue_received": False,
            "transport_cue_updated_at": None,
            "loop_active": False,
            "loop_active_midi": None,
            "loop_active_received": False,
            "loop_active_updated_at": None,
            "sync": False,
            "sync_midi": None,
            "sync_received": False,
            "sync_updated_at": None,
            "track_end_warning": False,
            "track_end_warning_midi": None,
            "track_end_warning_received": False,
            "track_end_warning_updated_at": None,
        }
    )
    return state


def update_deck_a(deck_a: dict[str, Any], message: mido.Message) -> bool:
    """Actualiza los mappings conocidos de Deck A en el canal MIDI 1."""
    if message.type != "control_change" or message.channel != 0:
        return False

    if message.control in DECK_A_CONTINUOUS_CONTROLS:
        key, _label = DECK_A_CONTINUOUS_CONTROLS[message.control]
        if deck_a[key]["midi"] == message.value:
            return False
        deck_a[key] = (
            make_loop_size_value(message.value)
            if key == "loop_size"
            else make_continuous_value(message.value)
        )
        return True

    if message.control in DECK_A_BOOLEAN_CONTROLS:
        key, _label = DECK_A_BOOLEAN_CONTROLS[message.control]
        if deck_a[f"{key}_midi"] == message.value:
            return False
        deck_a[key] = message.value > 0
        deck_a[f"{key}_midi"] = message.value
        deck_a[f"{key}_received"] = True
        deck_a[f"{key}_updated_at"] = iso_timestamp()
        return True

    return False


def update_deck_b(deck_b: dict[str, Any], message: mido.Message) -> bool:
    """Actualiza los mappings conocidos de Deck B en el canal MIDI 1."""
    if message.type != "control_change" or message.channel != 0:
        return False

    if message.control in DECK_B_CONTINUOUS_CONTROLS:
        key, _label = DECK_B_CONTINUOUS_CONTROLS[message.control]
        if deck_b[key]["midi"] == message.value:
            return False
        deck_b[key] = (
            make_loop_size_value(message.value)
            if key == "loop_size"
            else make_continuous_value(message.value)
        )
        return True

    if message.control in DECK_B_BOOLEAN_CONTROLS:
        key, _label = DECK_B_BOOLEAN_CONTROLS[message.control]
        if deck_b[f"{key}_midi"] == message.value:
            return False
        deck_b[key] = message.value > 0
        deck_b[f"{key}_midi"] = message.value
        deck_b[f"{key}_received"] = True
        deck_b[f"{key}_updated_at"] = iso_timestamp()
        return True

    return False


def update_crossfader(
    crossfader: dict[str, Any], message: mido.Message
) -> bool:
    """Actualiza la posición global del crossfader desde CC16."""
    if (
        message.type != "control_change"
        or message.channel != 0
        or message.control != CROSSFADER_CC
        or crossfader["midi"] == message.value
    ):
        return False

    crossfader.update(make_continuous_value(message.value))
    return True


def format_continuous_control(
    label: str, control: dict[str, Any] | None
) -> str:
    """Formatea una celda del dashboard; None significa control no mapeado."""
    if control is None or not control["received"]:
        return f"{label:<10} {'---':>3}   MIDI ---"
    return f"{label:<10} {control['percentage']:>3}%   MIDI {control['midi']:>3}"


def format_boolean_control(label: str, deck: dict[str, Any], key: str) -> str:
    if not deck[f"{key}_received"]:
        return f"{label:<10} {'---':>3}   MIDI ---"
    status = "ON" if deck[key] else "OFF"
    return f"{label:<10} {status:>3}   MIDI {deck[f'{key}_midi']:>3}"


def format_loop_size_control(deck: dict[str, Any]) -> str:
    control = deck["loop_size"]
    if not control["received"]:
        return f"{'LOOP SIZE':<10} {'---':>3}   MIDI ---"
    return f"{'LOOP SIZE':<10} {control['label']:<22} MIDI {control['midi']:>3}"


def format_crossfader(crossfader: dict[str, Any]) -> list[str]:
    """Representa MIDI 0 a la izquierda (A) y MIDI 127 a la derecha (B)."""
    if not crossfader["received"]:
        return [f"A [{'?' * CROSSFADER_WIDTH}] B", "---%   MIDI ---   SIN RECIBIR"]

    marker_index = round(float(crossfader["normalized"]) * (CROSSFADER_WIDTH - 1))
    track = (
        "-" * marker_index
        + "O"
        + "-" * (CROSSFADER_WIDTH - marker_index - 1)
    )
    midi_value = int(crossfader["midi"])
    if midi_value == 0:
        position = "DECK A"
    elif midi_value == 127:
        position = "DECK B"
    elif 63 <= midi_value <= 64:
        position = "CENTRO"
    elif midi_value < 64:
        position = "HACIA A"
    else:
        position = "HACIA B"

    return [
        f"A [{track}] B",
        f"{crossfader['percentage']:>3}% hacia B   MIDI {midi_value:>3}   {position}",
    ]


def message_target(message: mido.Message) -> tuple[str, str] | None:
    """Traduce un CC conocido a (sección, control) para el historial."""
    if message.type != "control_change" or message.channel != 0:
        return None
    if message.control in DECK_A_CONTINUOUS_CONTROLS:
        return "deck_a", DECK_A_CONTINUOUS_CONTROLS[message.control][0]
    if message.control in DECK_A_BOOLEAN_CONTROLS:
        return "deck_a", DECK_A_BOOLEAN_CONTROLS[message.control][0]
    if message.control in DECK_B_CONTINUOUS_CONTROLS:
        return "deck_b", DECK_B_CONTINUOUS_CONTROLS[message.control][0]
    if message.control in DECK_B_BOOLEAN_CONTROLS:
        return "deck_b", DECK_B_BOOLEAN_CONTROLS[message.control][0]
    if message.control == CROSSFADER_CC:
        return "mixer", "crossfader"
    return None


class SessionRecorder:
    """Mantiene el historial y guarda una sesión JSON al terminar."""

    def __init__(self) -> None:
        self.started_at = datetime.now().astimezone()
        self.started_monotonic = time.monotonic()
        self.events: list[dict[str, Any]] = []
        self.last_timing_event_at: dict[int, float] = {}

    def elapsed(self) -> float:
        return round(time.monotonic() - self.started_monotonic, 3)

    def record_midi(self, message: mido.Message) -> bool:
        target = message_target(message)
        if target is None:
            return False

        now = time.monotonic()
        if message.control in HIGH_FREQUENCY_CCS:
            last_recorded = self.last_timing_event_at.get(message.control)
            if (
                last_recorded is not None
                and now - last_recorded < TIMING_HISTORY_SAMPLE_SECONDS
            ):
                return False
            self.last_timing_event_at[message.control] = now

        section, control = target
        self.events.append(
            {
                "timestamp": iso_timestamp(),
                "elapsed_seconds": self.elapsed(),
                "type": "midi_change",
                "section": section,
                "control": control,
                "channel": message.channel + 1,
                "cc": message.control,
                "value": message.value,
            }
        )
        return True

    def record_analysis(self, event: dict[str, Any]) -> None:
        self.events.append(
            {
                "timestamp": iso_timestamp(),
                "elapsed_seconds": self.elapsed(),
                **event,
            }
        )

    def save(
        self,
        deck_a: dict[str, Any],
        deck_b: dict[str, Any],
        crossfader: dict[str, Any],
        midi_clock: dict[str, Any] | None = None,
        deck_tempos: dict[str, dict[str, Any]] | None = None,
    ) -> Path:
        ended_at = datetime.now().astimezone()
        transition_events = [
            event for event in self.events if event["type"] == "transition_ended"
        ]
        warnings = [event for event in self.events if event["type"] == "warning"]
        warnings_by_rule: dict[str, int] = {}
        for warning in warnings:
            rule = str(warning.get("rule", "unknown"))
            warnings_by_rule[rule] = warnings_by_rule.get(rule, 0) + 1
        payload = {
            "started_at": self.started_at.isoformat(timespec="milliseconds"),
            "ended_at": ended_at.isoformat(timespec="milliseconds"),
            "duration_seconds": round(
                (ended_at - self.started_at).total_seconds(), 3
            ),
            "summary": {
                "midi_changes": sum(
                    event["type"] == "midi_change" for event in self.events
                ),
                "transitions_completed": len(transition_events),
                "warnings": len(warnings),
                "warnings_by_rule": warnings_by_rule,
                "bass_overlap_warnings": warnings_by_rule.get("bass_overlap", 0),
            },
            "final_state": {
                "deck_a": deck_a,
                "deck_b": deck_b,
                "crossfader": crossfader,
                "midi_clock": {
                    key: value
                    for key, value in (midi_clock or {}).items()
                    if not key.startswith("_")
                },
                "deck_tempos": public_deck_tempos(deck_tempos or {}),
            },
            "events": self.events,
        }

        SESSION_DIRECTORY.mkdir(parents=True, exist_ok=True)
        filename = self.started_at.strftime("session_%Y%m%d_%H%M%S_%f.json")
        path = SESSION_DIRECTORY / filename
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return path


def create_coach_state() -> dict[str, Any]:
    return {
        "deck_a_audible": None,
        "deck_b_audible": None,
        "transition_active": False,
        "transition_started_at": None,
        "transition_end_candidate_at": None,
        "long_transition_warned": False,
        "timed_rules": {
            "bass_overlap": {"started_at": None, "warned": False, "last": None},
            "bass_gap": {"started_at": None, "warned": False, "last": None},
            "beats_out_of_phase": {
                "started_at": None,
                "warned": False,
                "last": None,
            },
            "track_end_a": {"started_at": None, "warned": False, "last": None},
            "track_end_b": {"started_at": None, "warned": False, "last": None},
            "silence_low_volumes": {
                "started_at": None,
                "warned": False,
                "last": None,
            },
            "silence_crossfader": {
                "started_at": None,
                "warned": False,
                "last": None,
            },
            "silence_eq_a": {"started_at": None, "warned": False, "last": None},
            "silence_eq_b": {"started_at": None, "warned": False, "last": None},
        },
        "motion_samples": {
            "deck_a_volume": [],
            "deck_b_volume": [],
            "crossfader": [],
        },
        "last_motion_warning_at": {},
        "warning_history": [],
        "feedback_override": None,
        "feedback_override_until": None,
        "feedback": "Esperando LOADED, PLAY, VOLUME y CROSSFADER...",
    }


def estimate_audible(
    deck: dict[str, Any], crossfader: dict[str, Any], side: str
) -> bool | None:
    """Estima audibilidad usando Loaded, Play, volumen y crossfader."""
    volume = deck["volume"]
    if (
        not deck["loaded_received"]
        or not deck["play_received"]
        or not volume["received"]
        or not crossfader["received"]
    ):
        return None

    loaded_and_playing = deck["loaded"] and deck["play"]
    volume_open = float(volume["normalized"]) > AUDIBLE_VOLUME_THRESHOLD
    cross_position = float(crossfader["normalized"])
    if side == "a":
        cross_allows_deck = cross_position < 1.0 - CROSSFADER_EDGE_THRESHOLD
    else:
        cross_allows_deck = cross_position > CROSSFADER_EDGE_THRESHOLD
    return loaded_and_playing and volume_open and cross_allows_deck


def emit_warning(
    coach: dict[str, Any],
    events: list[dict[str, Any]],
    rule: str,
    message: str,
    now: float,
) -> None:
    """Registra un aviso para sesión, dashboard e historial visible."""
    events.append({"type": "warning", "rule": rule, "message": message})
    coach["warning_history"].append(
        {"timestamp": iso_timestamp(), "rule": rule, "message": message}
    )
    coach["warning_history"] = coach["warning_history"][-8:]
    coach["feedback_override"] = f"AVISO: {message}"
    coach["feedback_override_until"] = now + WARNING_DISPLAY_SECONDS


def emit_positive_feedback(
    coach: dict[str, Any],
    events: list[dict[str, Any]],
    rule: str,
    message: str,
    now: float,
) -> None:
    """Registra la resolución positiva de un aviso anterior."""
    events.append({"type": "feedback", "rule": rule, "message": message})
    coach["warning_history"].append(
        {
            "timestamp": iso_timestamp(),
            "rule": rule,
            "message": message,
            "severity": "success",
        }
    )
    coach["warning_history"] = coach["warning_history"][-8:]
    coach["feedback_override"] = f"BIEN: {message}"
    coach["feedback_override_until"] = now + WARNING_DISPLAY_SECONDS


def timed_rule_fired(
    coach: dict[str, Any],
    rule: str,
    condition: bool,
    now: float,
    hold_seconds: float,
    cooldown_seconds: float,
) -> bool:
    """Devuelve True una vez por episodio tras mantener una condición."""
    state = coach["timed_rules"][rule]
    if not condition:
        state["started_at"] = None
        state["warned"] = False
        return False

    if state["started_at"] is None:
        state["started_at"] = now
        return False

    cooldown_ready = state["last"] is None or now - state["last"] >= cooldown_seconds
    if (
        not state["warned"]
        and now - state["started_at"] >= hold_seconds
        and cooldown_ready
    ):
        state["warned"] = True
        state["last"] = now
        return True
    return False


def phase_error_details(
    deck_a: dict[str, Any], deck_b: dict[str, Any]
) -> tuple[bool, str]:
    """Detecta desfase respecto del centro MIDI calibrado, sin asumir dirección."""
    offsets: list[tuple[str, float, int]] = []
    for name, deck in (("A", deck_a), ("B", deck_b)):
        phase = deck["phase"]
        if phase["received"]:
            midi_value = int(phase["midi"])
            offsets.append((name, abs(midi_value - PHASE_CENTER_MIDI), midi_value))

    if not offsets:
        return False, ""
    name, offset, midi_value = max(offsets, key=lambda item: item[1])
    return (
        offset >= PHASE_ERROR_THRESHOLD_MIDI,
        f"Deck {name} está fuera de fase (MIDI {midi_value}); corregí la alineación.",
    )


def deck_is_playing(deck: dict[str, Any]) -> bool:
    return bool(
        deck["loaded_received"]
        and deck["play_received"]
        and deck["loaded"]
        and deck["play"]
    )


def crossfader_allows(crossfader: dict[str, Any], side: str) -> bool:
    if not crossfader["received"]:
        return False
    position = float(crossfader["normalized"])
    if side == "a":
        return position < 1.0 - CROSSFADER_EDGE_THRESHOLD
    return position > CROSSFADER_EDGE_THRESHOLD


def volume_is_open(deck: dict[str, Any]) -> bool:
    return bool(
        deck["volume"]["received"]
        and float(deck["volume"]["normalized"]) > AUDIBLE_VOLUME_THRESHOLD
    )


def eq_is_fully_cut(deck: dict[str, Any]) -> bool:
    controls = (deck["low"], deck["mid"], deck["high"])
    return all(control["received"] for control in controls) and all(
        float(control["normalized"]) <= AUDIBLE_VOLUME_THRESHOLD
        for control in controls
    )


def abrupt_motion_warning(
    coach: dict[str, Any],
    key: str,
    label: str,
    control: dict[str, Any],
    enabled: bool,
    now: float,
) -> str | None:
    """Detecta un recorrido grande de fader dentro de una ventana corta."""
    samples: list[tuple[float, float]] = coach["motion_samples"][key]
    if not enabled or not control["received"]:
        samples.clear()
        return None

    value = float(control["normalized"])
    if not samples or samples[-1][1] != value:
        samples.append((now, value))
    samples[:] = [
        sample
        for sample in samples
        if now - sample[0] <= FADER_ABRUPT_WINDOW_SECONDS
    ]

    last_warning = coach["last_motion_warning_at"].get(key)
    cooldown_ready = (
        last_warning is None or now - last_warning >= FADER_WARNING_COOLDOWN_SECONDS
    )
    if (
        len(samples) >= 3
        and max(value for _at, value in samples)
        - min(value for _at, value in samples)
        >= FADER_ABRUPT_DELTA
        and cooldown_ready
    ):
        coach["last_motion_warning_at"][key] = now
        samples[:] = [(now, value)]
        return f"Movimiento abrupto en {label}; hacé el cambio más gradual."
    return None


def evaluate_coach(
    deck_a: dict[str, Any],
    deck_b: dict[str, Any],
    crossfader: dict[str, Any],
    coach: dict[str, Any],
    now: float | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Evalúa localmente los avisos que permiten los mappings actuales."""
    now = time.monotonic() if now is None else now
    changed = False
    events: list[dict[str, Any]] = []

    audible_a = estimate_audible(deck_a, crossfader, "a")
    audible_b = estimate_audible(deck_b, crossfader, "b")
    if (
        audible_a != coach["deck_a_audible"]
        or audible_b != coach["deck_b_audible"]
    ):
        coach["deck_a_audible"] = audible_a
        coach["deck_b_audible"] = audible_b
        changed = True

    both_audible = audible_a is True and audible_b is True
    if both_audible:
        coach["transition_end_candidate_at"] = None
        if not coach["transition_active"]:
            coach["transition_active"] = True
            coach["transition_started_at"] = now
            coach["long_transition_warned"] = False
            events.append({"type": "transition_started"})
            changed = True
        elif (
            not coach["long_transition_warned"]
            and now - coach["transition_started_at"] >= TRANSITION_TOO_SLOW_SECONDS
        ):
            coach["long_transition_warned"] = True
            emit_warning(
                coach,
                events,
                "transition_too_slow",
                "La transición lleva demasiado tiempo; definí qué deck queda sonando.",
                now,
            )
            changed = True
    elif coach["transition_active"]:
        if coach["transition_end_candidate_at"] is None:
            coach["transition_end_candidate_at"] = now
        elif now - coach["transition_end_candidate_at"] >= TRANSITION_END_HOLD_SECONDS:
            duration = round(
                max(
                    0.0,
                    now
                    - coach["transition_started_at"]
                    - TRANSITION_END_HOLD_SECONDS,
                ),
                3,
            )
            coach["transition_active"] = False
            coach["transition_started_at"] = None
            coach["transition_end_candidate_at"] = None
            coach["long_transition_warned"] = False
            events.append({"type": "transition_ended", "duration_seconds": duration})
            if 0 < duration < TRANSITION_TOO_FAST_SECONDS:
                emit_warning(
                    coach,
                    events,
                    "transition_too_fast",
                    f"La transición duró {duration:.1f}s; probá hacerla más progresiva.",
                    now,
                )
            changed = True

    lows_received = deck_a["low"]["received"] and deck_b["low"]["received"]
    bass_overlap = (
        both_audible
        and lows_received
        and float(deck_a["low"]["normalized"]) > BASS_HIGH_THRESHOLD
        and float(deck_b["low"]["normalized"]) > BASS_HIGH_THRESHOLD
    )
    bass_gap = (
        both_audible
        and lows_received
        and float(deck_a["low"]["normalized"]) < BASS_LOW_THRESHOLD
        and float(deck_b["low"]["normalized"]) < BASS_LOW_THRESHOLD
    )

    if timed_rule_fired(
        coach,
        "bass_overlap",
        bass_overlap,
        now,
        BASS_OVERLAP_HOLD_SECONDS,
        BASS_WARNING_COOLDOWN_SECONDS,
    ):
        emit_warning(
            coach,
            events,
            "bass_overlap",
            "Ambos graves están abiertos; bajá el LOW de uno de los decks.",
            now,
        )
        changed = True

    if timed_rule_fired(
        coach,
        "bass_gap",
        bass_gap,
        now,
        BASS_GAP_HOLD_SECONDS,
        BASS_WARNING_COOLDOWN_SECONDS,
    ):
        emit_warning(
            coach,
            events,
            "bass_gap",
            "Los dos LOW están cerrados; recuperá gradualmente el grave de un deck.",
            now,
        )
        changed = True

    phase_condition, phase_message = phase_error_details(deck_a, deck_b)
    phase_rule_state = coach["timed_rules"]["beats_out_of_phase"]
    phase_warning_was_active = bool(phase_rule_state["warned"])
    phase_warning_fired = timed_rule_fired(
        coach,
        "beats_out_of_phase",
        both_audible and phase_condition,
        now,
        PHASE_ERROR_HOLD_SECONDS,
        PHASE_WARNING_COOLDOWN_SECONDS,
    )
    if phase_warning_fired:
        emit_warning(
            coach,
            events,
            "beats_out_of_phase",
            phase_message,
            now,
        )
        changed = True
    elif (
        phase_warning_was_active
        and both_audible
        and not phase_condition
        and (deck_a["phase"]["received"] or deck_b["phase"]["received"])
    ):
        emit_positive_feedback(
            coach,
            events,
            "phase_recovered",
            "La fase volvió a una zona alineada.",
            now,
        )
        changed = True

    for rule, name, deck in (
        ("track_end_a", "A", deck_a),
        ("track_end_b", "B", deck_b),
    ):
        end_warning_active = (
            deck["track_end_warning_received"] and deck["track_end_warning"]
        )
        if timed_rule_fired(
            coach,
            rule,
            end_warning_active,
            now,
            0.0,
            TRACK_END_WARNING_COOLDOWN_SECONDS,
        ):
            emit_warning(
                coach,
                events,
                "track_end_warning",
                f"La canción del Deck {name} está por terminar; prepará la transición.",
                now,
            )
            changed = True

    playing = {
        "A": deck_is_playing(deck_a),
        "B": deck_is_playing(deck_b),
    }
    playing_decks = [
        ("A", "a", deck_a),
        ("B", "b", deck_b),
    ]
    active_decks = [item for item in playing_decks if playing[item[0]]]

    all_active_volumes_known = bool(active_decks) and all(
        deck["volume"]["received"] for _name, _side, deck in active_decks
    )
    active_volumes_closed = all_active_volumes_known and all(
        not volume_is_open(deck) for _name, _side, deck in active_decks
    )
    if timed_rule_fired(
        coach,
        "silence_low_volumes",
        active_volumes_closed,
        now,
        SILENCE_RISK_HOLD_SECONDS,
        SILENCE_WARNING_COOLDOWN_SECONDS,
    ):
        emit_warning(
            coach,
            events,
            "silence_low_volumes",
            "Riesgo de silencio: los decks en PLAY tienen el VOLUME cerrado.",
            now,
        )
        changed = True

    open_active_decks = [
        (name, side, deck)
        for name, side, deck in active_decks
        if volume_is_open(deck)
    ]
    crossfader_blocks_all = (
        bool(open_active_decks)
        and crossfader["received"]
        and all(
            not crossfader_allows(crossfader, side)
            for _name, side, _deck in open_active_decks
        )
    )
    blocked_names = " y ".join(
        f"Deck {name}" for name, _side, _deck in open_active_decks
    )
    if timed_rule_fired(
        coach,
        "silence_crossfader",
        crossfader_blocks_all,
        now,
        SILENCE_RISK_HOLD_SECONDS,
        SILENCE_WARNING_COOLDOWN_SECONDS,
    ):
        emit_warning(
            coach,
            events,
            "silence_crossfader",
            f"Riesgo de silencio: el crossfader está bloqueando {blocked_names}.",
            now,
        )
        changed = True

    for rule, name, side, deck in (
        ("silence_eq_a", "A", "a", deck_a),
        ("silence_eq_b", "B", "b", deck_b),
    ):
        eq_cut_condition = (
            playing[name]
            and volume_is_open(deck)
            and crossfader_allows(crossfader, side)
            and eq_is_fully_cut(deck)
        )
        if timed_rule_fired(
            coach,
            rule,
            eq_cut_condition,
            now,
            SILENCE_RISK_HOLD_SECONDS,
            SILENCE_WARNING_COOLDOWN_SECONDS,
        ):
            emit_warning(
                coach,
                events,
                "silence_eq_cut",
                f"Riesgo de silencio en Deck {name}: LOW, MID y HIGH están al mínimo.",
                now,
            )
            changed = True

    any_deck_playing = (
        deck_a["loaded"] and deck_a["play"]
    ) or (deck_b["loaded"] and deck_b["play"])
    motion_controls = (
        (
            "deck_a_volume",
            "VOLUME Deck A",
            deck_a["volume"],
            deck_a["loaded"] and deck_a["play"],
        ),
        (
            "deck_b_volume",
            "VOLUME Deck B",
            deck_b["volume"],
            deck_b["loaded"] and deck_b["play"],
        ),
        ("crossfader", "crossfader", crossfader, any_deck_playing),
    )
    for motion_key, label, control, enabled in motion_controls:
        motion_message = abrupt_motion_warning(
            coach, motion_key, label, control, enabled, now
        )
        if motion_message:
            emit_warning(
                coach,
                events,
                "fader_abrupt_change",
                motion_message,
                now,
            )
            changed = True

    override_active = (
        coach["feedback_override"] is not None
        and coach["feedback_override_until"] is not None
        and now < coach["feedback_override_until"]
    )
    if override_active:
        feedback = coach["feedback_override"]
    elif coach["transition_active"]:
        feedback = "Transición activa: ambos decks parecen audibles."
    elif audible_a is None or audible_b is None:
        feedback = "Esperando LOADED, PLAY, VOLUME y CROSSFADER..."
    else:
        feedback = "Mixer estable. Sin avisos."

    if not override_active and coach["feedback_override"] is not None:
        coach["feedback_override"] = None
        coach["feedback_override_until"] = None
        changed = True

    if feedback != coach["feedback"]:
        coach["feedback"] = feedback
        changed = True

    return changed, events


def render_dashboard(
    deck_a: dict[str, Any],
    deck_b: dict[str, Any],
    crossfader: dict[str, Any],
    coach: dict[str, Any],
    event_count: int,
    port_name: str,
    ansi_enabled: bool,
    raw_message: mido.Message | None = None,
    midi_clock: dict[str, Any] | None = None,
    deck_tempos: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Redibuja el dashboard sin acumular una línea por evento MIDI."""
    if midi_clock and midi_clock["received"]:
        bpm = f"{midi_clock['bpm']:.1f}" if midi_clock["bpm"] is not None else "calculando"
        clock_status = "ACTIVO" if midi_clock["active"] else "DETENIDO"
        clock_line = f"MIDI CLOCK: {bpm} BPM   {clock_status}"
    else:
        clock_line = "MIDI CLOCK: --- BPM   SIN RECIBIR"
    deck_tempos = deck_tempos or create_deck_tempos_state()

    def deck_bpm_text(
        side: str, deck: dict[str, Any]
    ) -> str:
        bpm, source, active = effective_deck_bpm(
            deck, deck_tempos[side], midi_clock or create_midi_clock_state()
        )
        if bpm is None:
            return "--- BPM"
        status = "ACTIVO" if active else "DETENIDO"
        return f"{bpm:.1f} BPM   {status} · {source}"

    def rhythm_text(side: str) -> str:
        tempo = deck_tempos[side]
        if tempo["downbeat_armed"]:
            return "Esperando próximo beat = 1/4"
        if not tempo["downbeat_set"]:
            return "Beat 1 sin marcar"
        blocks = tempo["bar_in_block"]
        return (
            f"Beat {tempo['beat_in_bar']}/4 · Compás {tempo['bar_count']} · "
            f"Bloques 4:{blocks['4']}/4 8:{blocks['8']}/8 "
            f"16:{blocks['16']}/16 32:{blocks['32']}/32"
        )

    lines = [
        "DJ COACH",
        "-" * 40,
        f"Puerto: {port_name}",
        clock_line,
        "",
        f"{'DECK A':<32}DECK B",
        f"{deck_bpm_text('a', deck_a):<42}{deck_bpm_text('b', deck_b)}",
        "",
    ]

    for key, label in DISPLAY_CONTROLS:
        left = format_continuous_control(label, deck_a.get(key))
        right = format_continuous_control(label, deck_b.get(key))
        lines.append(f"{left:<32}{right}")

    lines.extend(
        [
            "",
            f"{format_boolean_control('LOADED', deck_a, 'loaded'):<32}"
            f"{format_boolean_control('LOADED', deck_b, 'loaded')}",
            f"{format_boolean_control('PLAY', deck_a, 'play'):<32}"
            f"{format_boolean_control('PLAY', deck_b, 'play')}",
            f"{format_boolean_control('CUE PLAY', deck_a, 'transport_cue'):<32}"
            f"{format_boolean_control('CUE PLAY', deck_b, 'transport_cue')}",
            f"{format_boolean_control('LOOP', deck_a, 'loop_active'):<32}"
            f"{format_boolean_control('LOOP', deck_b, 'loop_active')}",
            f"{format_loop_size_control(deck_a):<44}"
            f"{format_loop_size_control(deck_b)}",
            f"{format_boolean_control('SYNC', deck_a, 'sync'):<32}"
            f"{format_boolean_control('SYNC', deck_b, 'sync')}",
            f"{format_boolean_control('FX ON', deck_a, 'fx_on'):<32}"
            f"{format_boolean_control('FX ON', deck_b, 'fx_on')}",
            f"{format_boolean_control('MON CUE', deck_a, 'cue'):<32}"
            f"{format_boolean_control('MON CUE', deck_b, 'cue')}",
            f"{format_boolean_control('TRACK END', deck_a, 'track_end_warning'):<32}"
            f"{format_boolean_control('TRACK END', deck_b, 'track_end_warning')}",
            "",
            f"{format_continuous_control('PROGRESO', deck_a['track_progress']):<32}"
            f"{format_continuous_control('PROGRESO', deck_b['track_progress'])}",
            "",
            f"{'TIMING MIDI (sin calibrar)':<32}TIMING MIDI (sin calibrar)",
        "",
        ]
    )

    for key, label in DISPLAY_TIMING_CONTROLS:
        left = format_continuous_control(label, deck_a.get(key))
        right = format_continuous_control(label, deck_b.get(key))
        lines.append(f"{left:<32}{right}")

    lines.extend(
        [
            "",
            "RITMO / COMPASES",
            f"Deck A: {rhythm_text('a')}",
            f"Deck B: {rhythm_text('b')}",
        ]
    )

    lines.extend(
        [
            "",
            "CROSSFADER",
            *format_crossfader(crossfader),
            "",
            "ESTADO LOCAL (con Play; todavía sin Deck Meter)",
            f"Deck A audible: {format_audible(coach['deck_a_audible'])}   "
            f"Deck B audible: {format_audible(coach['deck_b_audible'])}",
            f"Transición: {'ACTIVA' if coach['transition_active'] else 'NO'}",
            f"Coach: {coach['feedback']}",
            "",
            "AVISOS RECIENTES",
            *(
                [
                    f"- {warning['message']}"
                    for warning in reversed(coach["warning_history"][-3:])
                ]
                or ["- Sin avisos en esta sesión"]
            ),
            f"Eventos de sesión: {event_count}",
            "",
            "Ctrl+C para salir",
        ]
    )

    if raw_message is not None:
        lines.extend(["", f"DEBUG último mensaje: {raw_message}"])

    if ansi_enabled:
        print("\033[2J\033[H" + "\n".join(lines), end="", flush=True)
    else:
        os.system("cls" if os.name == "nt" else "clear")
        print("\n".join(lines), end="", flush=True)


def format_audible(value: bool | None) -> str:
    if value is None:
        return "---"
    return "SÍ" if value else "NO"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor MIDI de DJ Coach")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="muestra el último mensaje MIDI crudo recibido",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="imprime MIDI crudo, ocultando los pulsos continuos de MIDI Clock",
    )
    parser.add_argument(
        "--raw-all",
        action="store_true",
        help="con --raw, incluye también los pulsos continuos de MIDI Clock",
    )
    return parser.parse_args()


def should_print_raw_message(message: mido.Message, include_clock: bool = False) -> bool:
    """Evita que los 24 pulsos por beat del reloj oculten mensajes útiles."""
    return include_clock or message.type != "clock"


def run_raw_monitor(port_name: str, include_clock: bool = False) -> int:
    """Modo mínimo de diagnóstico con la lectura que se validó inicialmente."""
    print(f"\nConectado a: {port_name}")
    clock_note = "incluido" if include_clock else "oculto"
    print(f"Modo MIDI crudo (MIDI Clock {clock_note}; Ctrl+C para salir)...\n")
    try:
        with mido.open_input(port_name) as port:
            for message in port:
                if should_print_raw_message(message, include_clock):
                    print(message, flush=True)
    except KeyboardInterrupt:
        print("\nMonitor MIDI detenido.")
    except Exception as exc:
        print(f"\nError al leer el puerto MIDI: {exc}", file=sys.stderr)
        return 1
    return 0


def read_midi_messages(
    port: mido.ports.BaseInput,
    incoming_messages: queue.Queue[TimedMidiMessage],
) -> None:
    """Lee MIDI con el iterador bloqueante estable y lo entrega al dashboard."""
    try:
        for message in port:
            incoming_messages.put(TimedMidiMessage(message, time.monotonic()))
    except (OSError, ValueError):
        # El puerto puede cerrarse mientras este hilo espera al salir con Ctrl+C.
        return


def main() -> int:
    args = parse_args()

    try:
        ports = mido.get_input_names()
    except Exception as exc:
        print(f"Error al consultar los puertos MIDI: {exc}", file=sys.stderr)
        print(
            "Comprobá que python-rtmidi esté instalado para Python 3.12.",
            file=sys.stderr,
        )
        return 1

    print("Puertos MIDI disponibles:")
    if ports:
        for name in ports:
            print(f" - {name}")
    else:
        print(" (ninguno)")

    port_name = find_djcoach_port(ports)
    if port_name is None:
        print(
            "\nNo se encontró un puerto MIDI que contenga 'djCoach'.\n"
            "Abrí loopMIDI, comprobá que el puerto djCoach exista y volvé a ejecutar "
            "el programa.",
            file=sys.stderr,
        )
        return 1

    if args.raw:
        return run_raw_monitor(port_name, include_clock=args.raw_all)

    deck_a = create_deck_a_state()
    deck_b = create_deck_b_state()
    crossfader = make_continuous_value()
    midi_clock = create_midi_clock_state()
    deck_tempos = create_deck_tempos_state()
    coach = create_coach_state()
    recorder = SessionRecorder()
    ansi_enabled = enable_ansi_on_windows()
    render_dashboard(
        deck_a,
        deck_b,
        crossfader,
        coach,
        len(recorder.events),
        port_name,
        ansi_enabled,
        midi_clock=midi_clock,
        deck_tempos=deck_tempos,
    )

    exit_code = 0
    incoming_messages: queue.Queue[TimedMidiMessage] = queue.Queue()
    dashboard_dirty = False
    last_dashboard_render_at = time.monotonic()
    last_raw_message: mido.Message | None = None
    try:
        with mido.open_input(port_name) as port:
            reader_thread = threading.Thread(
                target=read_midi_messages,
                args=(port, incoming_messages),
                name="dj-coach-midi-reader",
                daemon=True,
            )
            reader_thread.start()
            while True:
                try:
                    first_message = incoming_messages.get(
                        timeout=POLL_INTERVAL_SECONDS
                    )
                except queue.Empty:
                    first_message = None

                envelopes: list[TimedMidiMessage] = []
                if first_message is not None:
                    envelopes.append(first_message)
                    while True:
                        try:
                            envelopes.append(incoming_messages.get_nowait())
                        except queue.Empty:
                            break

                updated = False
                for envelope in envelopes:
                    message = envelope.message
                    message_updated = any(
                        (
                            update_deck_a(deck_a, message),
                            update_deck_b(deck_b, message),
                            update_crossfader(crossfader, message),
                            update_midi_clock(
                                midi_clock, message, envelope.received_at
                            ),
                            update_deck_tempo_from_beat_phase(
                                deck_tempos, message, envelope.received_at
                            ),
                        )
                    )
                    if message_updated:
                        recorder.record_midi(message)
                        updated = True
                    last_raw_message = message

                clock_changed = refresh_midi_clock(midi_clock)
                tempos_changed = refresh_deck_tempos(deck_tempos)

                coach_changed, analysis_events = evaluate_coach(
                    deck_a, deck_b, crossfader, coach
                )
                for event in analysis_events:
                    recorder.record_analysis(event)

                if (
                    updated
                    or clock_changed
                    or tempos_changed
                    or coach_changed
                    or (args.debug and envelopes)
                ):
                    dashboard_dirty = True

                now = time.monotonic()
                if (
                    dashboard_dirty
                    and now - last_dashboard_render_at >= DASHBOARD_REFRESH_SECONDS
                ):
                    render_dashboard(
                        deck_a,
                        deck_b,
                        crossfader,
                        coach,
                        len(recorder.events),
                        port_name,
                        ansi_enabled,
                        raw_message=last_raw_message if args.debug else None,
                        midi_clock=midi_clock,
                        deck_tempos=deck_tempos,
                    )
                    dashboard_dirty = False
                    last_dashboard_render_at = now
    except KeyboardInterrupt:
        print("\nDJ Coach detenido.")
    except Exception as exc:
        print(f"\nError al abrir o leer el puerto MIDI: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        try:
            session_path = recorder.save(
                deck_a, deck_b, crossfader, midi_clock, deck_tempos
            )
            print(f"\nSesión guardada en: {session_path}")
        except Exception as exc:
            print(f"\nNo se pudo guardar la sesión: {exc}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
