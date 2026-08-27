"""Orquestación de una toma de referencia capturada desde el runtime MIDI."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from djcoach.domain import Take, TakeRole

from .repository import LessonRepository
from .take_repository import TakeRepository


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class ActiveReferenceRecording:
    lesson_id: str
    take: Take
    checkpoint: dict[str, Any]
    started_monotonic: float


class ReferenceTakeRecorder:
    """Permite una sola grabación activa para el puerto MIDI compartido."""

    def __init__(
        self,
        runtime: Any,
        lesson_repository: LessonRepository,
        take_repository: TakeRepository | None = None,
    ) -> None:
        self.runtime = runtime
        self.lesson_repository = lesson_repository
        self.take_repository = take_repository or TakeRepository()
        self.lock = threading.RLock()
        self.active: ActiveReferenceRecording | None = None

    def start(self, lesson_id: str) -> Take:
        with self.lock:
            if self.active is not None:
                raise RuntimeError(
                    "Ya hay una grabación activa. Detenela antes de iniciar otra."
                )
            self.lesson_repository.get(lesson_id)
            checkpoint = self.runtime.begin_take_capture()
            snapshot = checkpoint["initial_state"]
            if snapshot["status"] != "connected":
                raise RuntimeError("El puerto MIDI djCoach no está conectado.")
            if not (
                snapshot["deck_a"]["loaded_received"]
                and snapshot["deck_a"]["loaded"]
                and snapshot["deck_b"]["loaded_received"]
                and snapshot["deck_b"]["loaded"]
            ):
                raise RuntimeError("Los dos decks deben informar LOADED antes de grabar.")

            take = Take(
                lesson_id=lesson_id,
                role=TakeRole.TEACHER,
                initial_state=snapshot,
            )
            self.active = ActiveReferenceRecording(
                lesson_id=lesson_id,
                take=take,
                checkpoint=checkpoint,
                started_monotonic=time.monotonic(),
            )
            return take

    def stop(self, lesson_id: str) -> Take:
        with self.lock:
            if self.active is None or self.active.lesson_id != lesson_id:
                raise RuntimeError("Esta lección no tiene una grabación activa.")

            active = self.active
            result = self.runtime.finish_take_capture(active.checkpoint)
            active.take.ended_at = timestamp_now()
            active.take.duration_seconds = round(
                time.monotonic() - active.started_monotonic, 3
            )
            active.take.events = result["events"]
            active.take.final_state = result["final_state"]
            active.take.features = {
                "event_count": len(active.take.events),
                "midi_change_count": sum(
                    event.get("type") == "midi_change"
                    for event in active.take.events
                ),
            }

            self.take_repository.save(active.take)
            lesson = self.lesson_repository.get(lesson_id)
            lesson.reference_take_id = active.take.id
            lesson.status = "reference_recorded"
            lesson.updated_at = timestamp_now()
            self.lesson_repository.save(lesson)
            self.active = None
            return active.take

    def status(self, lesson_id: str) -> dict[str, Any]:
        with self.lock:
            if self.active is not None and self.active.lesson_id == lesson_id:
                return {
                    "state": "recording",
                    "take_id": self.active.take.id,
                    "elapsed_seconds": round(
                        time.monotonic() - self.active.started_monotonic, 1
                    ),
                    "event_count": self.runtime.take_event_count(
                        self.active.checkpoint
                    ),
                }
            if self.active is not None:
                return {
                    "state": "locked",
                    "take_id": None,
                    "active_lesson_id": self.active.lesson_id,
                    "elapsed_seconds": 0.0,
                    "event_count": 0,
                }
            lesson = self.lesson_repository.get(lesson_id)
            if lesson.reference_take_id:
                take = self.take_repository.get(lesson.reference_take_id)
                return {
                    "state": "recorded",
                    "take_id": take.id,
                    "elapsed_seconds": take.duration_seconds or 0.0,
                    "event_count": len(take.events),
                }
            return {
                "state": "idle",
                "take_id": None,
                "elapsed_seconds": 0.0,
                "event_count": 0,
            }
