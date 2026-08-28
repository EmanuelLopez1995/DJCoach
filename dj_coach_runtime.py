"""Runtime compartido para exponer DJ Coach a interfaces no bloqueantes."""

from __future__ import annotations

import copy
import queue
import threading
from typing import Any

import mido

from dj_coach import (
    POLL_INTERVAL_SECONDS,
    SessionRecorder,
    TimedMidiMessage,
    arm_deck_downbeat,
    create_coach_state,
    create_deck_a_state,
    create_deck_b_state,
    create_deck_tempos_state,
    create_midi_clock_state,
    evaluate_coach,
    find_djcoach_port,
    iso_timestamp,
    make_continuous_value,
    read_midi_messages,
    refresh_deck_tempos,
    refresh_midi_clock,
    reset_deck_rhythm,
    update_crossfader,
    update_deck_a,
    update_deck_b,
    update_deck_tempo_from_beat_phase,
    update_midi_clock,
)


class DJCoachRuntime:
    """Mantiene MIDI, reglas y sesión en segundo plano para una interfaz web."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.incoming: queue.Queue[TimedMidiMessage] = queue.Queue()
        self.deck_a = create_deck_a_state()
        self.deck_b = create_deck_b_state()
        self.crossfader = make_continuous_value()
        self.midi_clock = create_midi_clock_state()
        self.deck_tempos = create_deck_tempos_state()
        self.coach = create_coach_state()
        self.recorder = SessionRecorder()
        self.status = "starting"
        self.error: str | None = None
        self.port_name: str | None = None
        self.last_raw_message: str | None = None
        self.last_midi_at: str | None = None
        self.saved_session_path: str | None = None
        self.port: mido.ports.BaseInput | None = None
        self.reader_thread: threading.Thread | None = None
        self.worker_thread: threading.Thread | None = None
        self.connector_thread: threading.Thread | None = None
        self._started = False
        self._stopped = False

    def start(self) -> None:
        with self.lock:
            if self._started:
                return
            self._started = True

        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="dj-coach-web-state-worker",
            daemon=True,
        )
        self.worker_thread.start()
        self.connector_thread = threading.Thread(
            target=self._connect_loop,
            name="dj-coach-web-midi-connector",
            daemon=True,
        )
        self.connector_thread.start()

    def _connect_loop(self) -> None:
        """Reintenta el puerto tras una recarga o un reinicio de loopMIDI."""
        while not self.stop_event.is_set():
            with self.lock:
                already_connected = self.port is not None
            if already_connected:
                self.stop_event.wait(0.5)
                continue
            try:
                port_names = mido.get_input_names()
                port_name = find_djcoach_port(port_names)
                if port_name is None:
                    raise RuntimeError("No se encontró el puerto djCoach.")
                port = mido.open_input(port_name)
            except Exception as exc:
                with self.lock:
                    self.status = "reconnecting"
                    self.error = str(exc)
                self.stop_event.wait(1.0)
                continue

            with self.lock:
                if self.stop_event.is_set():
                    port.close()
                    return
                self.port_name = port_name
                self.port = port
                self.status = "connected"
                self.error = None
                self.reader_thread = threading.Thread(
                    target=self._read_port,
                    args=(port,),
                    name="dj-coach-web-midi-reader",
                    daemon=True,
                )
                self.reader_thread.start()

    def _read_port(self, port: mido.ports.BaseInput) -> None:
        """Libera el puerto para que el conector pueda recuperarlo si se corta."""
        read_midi_messages(port, self.incoming)
        with self.lock:
            if self.port is port:
                self.port = None
                if not self.stop_event.is_set():
                    self.status = "reconnecting"
                    self.error = "La conexi\u00f3n MIDI se reinici\u00f3; reconectando..."
        try:
            port.close()
        except Exception:
            pass

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                first_message = self.incoming.get(timeout=POLL_INTERVAL_SECONDS)
            except queue.Empty:
                first_message = None

            envelopes = []
            if first_message is not None:
                envelopes.append(first_message)
                while True:
                    try:
                        envelopes.append(self.incoming.get_nowait())
                    except queue.Empty:
                        break

            with self.lock:
                for envelope in envelopes:
                    message = envelope.message
                    updated = any(
                        (
                            update_deck_a(self.deck_a, message),
                            update_deck_b(self.deck_b, message),
                            update_crossfader(self.crossfader, message),
                            update_midi_clock(
                                self.midi_clock, message, envelope.received_at
                            ),
                            update_deck_tempo_from_beat_phase(
                                self.deck_tempos, message, envelope.received_at
                            ),
                        )
                    )
                    if updated:
                        self.recorder.record_midi(message)
                    self.last_raw_message = str(message)
                    self.last_midi_at = iso_timestamp()

                refresh_midi_clock(self.midi_clock)
                refresh_deck_tempos(self.deck_tempos)

                _changed, analysis_events = evaluate_coach(
                    self.deck_a,
                    self.deck_b,
                    self.crossfader,
                    self.coach,
                )
                for event in analysis_events:
                    self.recorder.record_analysis(event)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "error": self.error,
                "port_name": self.port_name,
                "deck_a": copy.deepcopy(self.deck_a),
                "deck_b": copy.deepcopy(self.deck_b),
                "crossfader": copy.deepcopy(self.crossfader),
                "midi_clock": {
                    key: copy.deepcopy(value)
                    for key, value in self.midi_clock.items()
                    if not key.startswith("_")
                },
                "deck_tempos": {
                    side: {
                        key: copy.deepcopy(value)
                        for key, value in tempo.items()
                        if not key.startswith("_")
                    }
                    for side, tempo in self.deck_tempos.items()
                },
                "coach": copy.deepcopy(self.coach),
                "event_count": len(self.recorder.events),
                "last_raw_message": self.last_raw_message,
                "last_midi_at": self.last_midi_at,
                "saved_session_path": self.saved_session_path,
            }

    def begin_take_capture(self) -> dict[str, Any]:
        """Crea un punto de corte atómico para una futura toma de lección."""
        with self.lock:
            return {
                "event_cursor": len(self.recorder.events),
                "elapsed_seconds": self.recorder.elapsed(),
                "initial_state": self.snapshot(),
            }

    def finish_take_capture(
        self, checkpoint: dict[str, Any]
    ) -> dict[str, Any]:
        """Devuelve eventos posteriores al corte, con tiempo relativo a la toma."""
        with self.lock:
            cursor = int(checkpoint["event_cursor"])
            baseline = float(checkpoint["elapsed_seconds"])
            events = copy.deepcopy(self.recorder.events[cursor:])
            for event in events:
                if "elapsed_seconds" in event:
                    event["elapsed_seconds"] = round(
                        max(0.0, float(event["elapsed_seconds"]) - baseline), 3
                    )
            return {
                "events": events,
                "final_state": self.snapshot(),
            }

    def peek_take_capture(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """Consulta una captura activa sin cerrarla ni alterar sus eventos."""
        with self.lock:
            result = self.finish_take_capture(checkpoint)
            result["elapsed_seconds"] = round(
                max(
                    0.0,
                    self.recorder.elapsed()
                    - float(checkpoint["elapsed_seconds"]),
                ),
                3,
            )
            return result

    def take_event_count(self, checkpoint: dict[str, Any]) -> int:
        with self.lock:
            cursor = int(checkpoint["event_cursor"])
            return max(0, len(self.recorder.events) - cursor)

    def arm_downbeat(self, side: str) -> None:
        with self.lock:
            arm_deck_downbeat(self.deck_tempos, side)

    def clear_downbeat(self, side: str) -> None:
        with self.lock:
            if side not in self.deck_tempos:
                raise ValueError("El deck debe ser 'a' o 'b'.")
            reset_deck_rhythm(self.deck_tempos[side])

    def stop(self) -> None:
        with self.lock:
            if self._stopped:
                return
            self._stopped = True
            self.stop_event.set()
            port = self.port

        if port is not None:
            try:
                port.close()
            except Exception:
                pass

        if self.worker_thread is not None:
            self.worker_thread.join(timeout=2)
        if self.connector_thread is not None:
            self.connector_thread.join(timeout=2)
        if self.reader_thread is not None:
            self.reader_thread.join(timeout=2)

        with self.lock:
            try:
                path = self.recorder.save(
                    self.deck_a,
                    self.deck_b,
                    self.crossfader,
                    self.midi_clock,
                    self.deck_tempos,
                )
                self.saved_session_path = str(path)
            except Exception as exc:
                self.error = f"No se pudo guardar la sesión: {exc}"
            self.status = "stopped"
