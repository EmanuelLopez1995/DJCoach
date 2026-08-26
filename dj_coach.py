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
from datetime import datetime
from pathlib import Path
from typing import Any

import mido


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
}

DECK_A_BOOLEAN_CONTROLS = {
    7: ("fx_on", "FX"),
    8: ("cue", "CUE"),
    18: ("play", "PLAY"),
    20: ("loaded", "LOADED"),
    22: ("transport_cue", "CUE"),
    24: ("loop_active", "LOOP"),
    26: ("sync", "SYNC"),
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
}

DECK_B_BOOLEAN_CONTROLS = {
    14: ("fx_on", "FX"),
    15: ("cue", "CUE"),
    19: ("play", "PLAY"),
    21: ("loaded", "LOADED"),
    23: ("transport_cue", "CUE"),
    25: ("loop_active", "LOOP"),
    27: ("sync", "SYNC"),
}

CROSSFADER_CC = 16
CROSSFADER_WIDTH = 25
POLL_INTERVAL_SECONDS = 0.02
DASHBOARD_REFRESH_SECONDS = 0.05
TIMING_HISTORY_SAMPLE_SECONDS = 0.10
HIGH_FREQUENCY_CCS = {28, 29, 30, 31}

AUDIBLE_VOLUME_THRESHOLD = 0.05
CROSSFADER_EDGE_THRESHOLD = 0.05
BASS_HIGH_THRESHOLD = 0.80
BASS_OVERLAP_HOLD_SECONDS = 1.5
BASS_WARNING_COOLDOWN_SECONDS = 8.0
TRANSITION_END_HOLD_SECONDS = 1.0

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


def create_deck_a_state() -> dict[str, Any]:
    """Crea el estado inicial de los controles mapeados del Deck A."""
    state: dict[str, Any] = {
        key: make_continuous_value()
        for key, _label in DECK_A_CONTINUOUS_CONTROLS.values()
    }
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
        }
    )
    return state


def create_deck_b_state() -> dict[str, Any]:
    """Crea el estado inicial de los controles mapeados del Deck B."""
    state: dict[str, Any] = {
        key: make_continuous_value()
        for key, _label in DECK_B_CONTINUOUS_CONTROLS.values()
    }
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
        deck_a[key] = make_continuous_value(message.value)
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
        deck_b[key] = make_continuous_value(message.value)
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
    ) -> Path:
        ended_at = datetime.now().astimezone()
        transition_events = [
            event for event in self.events if event["type"] == "transition_ended"
        ]
        warnings = [event for event in self.events if event["type"] == "warning"]
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
                "bass_overlap_warnings": sum(
                    event.get("rule") == "bass_overlap" for event in warnings
                ),
            },
            "final_state": {
                "deck_a": deck_a,
                "deck_b": deck_b,
                "crossfader": crossfader,
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
        "bass_candidate_at": None,
        "bass_warned_this_episode": False,
        "last_bass_warning_at": None,
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


def evaluate_coach(
    deck_a: dict[str, Any],
    deck_b: dict[str, Any],
    crossfader: dict[str, Any],
    coach: dict[str, Any],
    now: float | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Evalúa transiciones y bass_overlap sin depender de una IA."""
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
            events.append({"type": "transition_started"})
            changed = True
    elif coach["transition_active"]:
        if coach["transition_end_candidate_at"] is None:
            coach["transition_end_candidate_at"] = now
        elif now - coach["transition_end_candidate_at"] >= TRANSITION_END_HOLD_SECONDS:
            duration = round(now - coach["transition_started_at"], 3)
            coach["transition_active"] = False
            coach["transition_started_at"] = None
            coach["transition_end_candidate_at"] = None
            events.append({"type": "transition_ended", "duration_seconds": duration})
            changed = True

    lows_received = deck_a["low"]["received"] and deck_b["low"]["received"]
    bass_condition = (
        both_audible
        and lows_received
        and float(deck_a["low"]["normalized"]) > BASS_HIGH_THRESHOLD
        and float(deck_b["low"]["normalized"]) > BASS_HIGH_THRESHOLD
    )

    if not bass_condition:
        coach["bass_candidate_at"] = None
        if coach["bass_warned_this_episode"]:
            coach["bass_warned_this_episode"] = False
            changed = True
    elif coach["bass_candidate_at"] is None:
        coach["bass_candidate_at"] = now
    elif (
        not coach["bass_warned_this_episode"]
        and now - coach["bass_candidate_at"] >= BASS_OVERLAP_HOLD_SECONDS
        and (
            coach["last_bass_warning_at"] is None
            or now - coach["last_bass_warning_at"] >= BASS_WARNING_COOLDOWN_SECONDS
        )
    ):
        coach["bass_warned_this_episode"] = True
        coach["last_bass_warning_at"] = now
        events.append(
            {
                "type": "warning",
                "rule": "bass_overlap",
                "message": "Ambos LOW están altos y los dos decks parecen audibles.",
            }
        )
        changed = True

    if coach["bass_warned_this_episode"]:
        feedback = "AVISO: bajá el LOW de uno de los decks; ambos graves están abiertos."
    elif coach["transition_active"]:
        feedback = "Transición activa: ambos decks parecen audibles."
    elif audible_a is None or audible_b is None:
        feedback = "Esperando LOADED, PLAY, VOLUME y CROSSFADER..."
    else:
        feedback = "Mixer estable. Sin avisos."

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
) -> None:
    """Redibuja el dashboard sin acumular una línea por evento MIDI."""
    lines = [
        "DJ COACH",
        "-" * 40,
        f"Puerto: {port_name}",
        "",
        f"{'DECK A':<32}DECK B",
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
            f"{format_boolean_control('SYNC', deck_a, 'sync'):<32}"
            f"{format_boolean_control('SYNC', deck_b, 'sync')}",
            f"{format_boolean_control('FX ON', deck_a, 'fx_on'):<32}"
            f"{format_boolean_control('FX ON', deck_b, 'fx_on')}",
            f"{format_boolean_control('MON CUE', deck_a, 'cue'):<32}"
            f"{format_boolean_control('MON CUE', deck_b, 'cue')}",
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
            "CROSSFADER",
            *format_crossfader(crossfader),
            "",
            "ESTADO LOCAL (con Play; todavía sin Deck Meter)",
            f"Deck A audible: {format_audible(coach['deck_a_audible'])}   "
            f"Deck B audible: {format_audible(coach['deck_b_audible'])}",
            f"Transición: {'ACTIVA' if coach['transition_active'] else 'NO'}",
            f"Coach: {coach['feedback']}",
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
        help="imprime únicamente MIDI crudo usando el lector bloqueante original",
    )
    return parser.parse_args()


def run_raw_monitor(port_name: str) -> int:
    """Modo mínimo de diagnóstico con la lectura que se validó inicialmente."""
    print(f"\nConectado a: {port_name}")
    print("Modo MIDI crudo (Ctrl+C para salir)...\n")
    try:
        with mido.open_input(port_name) as port:
            for message in port:
                print(message, flush=True)
    except KeyboardInterrupt:
        print("\nMonitor MIDI detenido.")
    except Exception as exc:
        print(f"\nError al leer el puerto MIDI: {exc}", file=sys.stderr)
        return 1
    return 0


def read_midi_messages(
    port: mido.ports.BaseInput,
    incoming_messages: queue.Queue[mido.Message],
) -> None:
    """Lee MIDI con el iterador bloqueante estable y lo entrega al dashboard."""
    try:
        for message in port:
            incoming_messages.put(message)
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
        return run_raw_monitor(port_name)

    deck_a = create_deck_a_state()
    deck_b = create_deck_b_state()
    crossfader = make_continuous_value()
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
    )

    exit_code = 0
    incoming_messages: queue.Queue[mido.Message] = queue.Queue()
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

                messages: list[mido.Message] = []
                if first_message is not None:
                    messages.append(first_message)
                    while True:
                        try:
                            messages.append(incoming_messages.get_nowait())
                        except queue.Empty:
                            break

                updated = False
                for message in messages:
                    message_updated = any(
                        (
                            update_deck_a(deck_a, message),
                            update_deck_b(deck_b, message),
                            update_crossfader(crossfader, message),
                        )
                    )
                    if message_updated:
                        recorder.record_midi(message)
                        updated = True
                    last_raw_message = message

                coach_changed, analysis_events = evaluate_coach(
                    deck_a, deck_b, crossfader, coach
                )
                for event in analysis_events:
                    recorder.record_analysis(event)

                if updated or coach_changed or (args.debug and messages):
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
            session_path = recorder.save(deck_a, deck_b, crossfader)
            print(f"\nSesión guardada en: {session_path}")
        except Exception as exc:
            print(f"\nNo se pudo guardar la sesión: {exc}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
