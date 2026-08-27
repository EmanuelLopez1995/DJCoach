"""Grabación y seguimiento en vivo de una práctica guiada."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from djcoach.domain import Take, TakeRole

from .attempt_repository import AttemptRepository
from .guidance import GUIDANCE_SCHEMA_VERSION, build_guidance_steps, event_matches_step
from .repository import LessonRepository
from .take_repository import TakeRepository


MISSED_AFTER_SECONDS = 15.0
ON_TIME_TOLERANCE_SECONDS = 5.0
EARLY_ACTION_WINDOW_SECONDS = 10.0


def _timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class ActiveStudentAttempt:
    lesson_id: str
    take: Take
    checkpoint: dict[str, Any]
    steps: list[dict[str, Any]]
    started_monotonic: float
    processed_event_count: int = 0
    anchor_elapsed_seconds: float | None = None
    current_index: int = 0
    outcomes: list[dict[str, Any]] = field(default_factory=list)


class GuidedPracticeRecorder:
    def __init__(
        self,
        runtime: Any,
        lesson_repository: LessonRepository,
        reference_repository: TakeRepository,
        attempt_repository: AttemptRepository | None = None,
    ) -> None:
        self.runtime = runtime
        self.lesson_repository = lesson_repository
        self.reference_repository = reference_repository
        self.attempt_repository = attempt_repository or AttemptRepository()
        self.lock = threading.RLock()
        self.active: ActiveStudentAttempt | None = None

    def start(self, lesson_id: str) -> Take:
        with self.lock:
            if self.active is not None:
                raise RuntimeError("Ya hay un intento del alumno en curso.")
            lesson = self.lesson_repository.get(lesson_id)
            if lesson.status != "ready_for_practice" or not lesson.reference_take_id:
                raise RuntimeError("La referencia debe estar aprobada antes de practicar.")
            reference = self.reference_repository.get(lesson.reference_take_id)
            steps = build_guidance_steps(reference.features)
            if not steps:
                raise RuntimeError("La referencia no contiene consignas practicables.")

            checkpoint = self.runtime.begin_take_capture()
            snapshot = checkpoint["initial_state"]
            if snapshot["status"] != "connected":
                raise RuntimeError("El puerto MIDI djCoach no está conectado.")
            if not all(
                (
                    snapshot["deck_a"]["loaded_received"],
                    snapshot["deck_a"]["loaded"],
                    snapshot["deck_b"]["loaded_received"],
                    snapshot["deck_b"]["loaded"],
                )
            ):
                raise RuntimeError("Los dos decks deben informar LOADED antes de practicar.")

            take = Take(
                lesson_id=lesson_id,
                role=TakeRole.STUDENT,
                initial_state=snapshot,
            )
            self.active = ActiveStudentAttempt(
                lesson_id=lesson_id,
                take=take,
                checkpoint=checkpoint,
                steps=steps,
                started_monotonic=time.monotonic(),
            )
            return take

    def _mark_missed_until(
        self, active: ActiveStudentAttempt, student_seconds: float
    ) -> None:
        while active.current_index < len(active.steps):
            step = active.steps[active.current_index]
            if student_seconds <= step["reference_seconds"] + MISSED_AFTER_SECONDS:
                break
            active.outcomes.append(
                {
                    "step_id": step["id"],
                    "status": "missed",
                    "timing": None,
                    "student_seconds": None,
                    "delta_seconds": None,
                }
            )
            active.current_index += 1

    def _refresh(self, active: ActiveStudentAttempt) -> dict[str, Any]:
        capture = self.runtime.peek_take_capture(active.checkpoint)
        events = capture["events"]
        new_events = events[active.processed_event_count :]
        for event in new_events:
            event_elapsed = float(event.get("elapsed_seconds", 0.0))
            if active.anchor_elapsed_seconds is None:
                if (
                    event.get("type") == "midi_change"
                    and event.get("section") == "deck_a"
                    and event.get("control") == "play"
                    and int(event.get("value", 0)) >= 64
                ):
                    active.anchor_elapsed_seconds = event_elapsed
                continue

            student_seconds = max(
                0.0, event_elapsed - active.anchor_elapsed_seconds
            )
            self._mark_missed_until(active, student_seconds)
            if active.current_index >= len(active.steps):
                continue
            matched_index = next(
                (
                    index
                    for index in range(active.current_index, len(active.steps))
                    if active.steps[index]["reference_seconds"]
                    <= student_seconds + EARLY_ACTION_WINDOW_SECONDS
                    and event_matches_step(event, active.steps[index])
                ),
                None,
            )
            if matched_index is not None:
                while active.current_index < matched_index:
                    skipped = active.steps[active.current_index]
                    active.outcomes.append(
                        {
                            "step_id": skipped["id"],
                            "status": "missed",
                            "timing": None,
                            "student_seconds": None,
                            "delta_seconds": None,
                        }
                    )
                    active.current_index += 1
                step = active.steps[active.current_index]
                delta = round(student_seconds - step["reference_seconds"], 3)
                if delta < -ON_TIME_TOLERANCE_SECONDS:
                    timing = "early"
                elif delta > ON_TIME_TOLERANCE_SECONDS:
                    timing = "late"
                else:
                    timing = "on_time"
                active.outcomes.append(
                    {
                        "step_id": step["id"],
                        "status": "completed",
                        "timing": timing,
                        "student_seconds": round(student_seconds, 3),
                        "delta_seconds": delta,
                    }
                )
                active.current_index += 1

        active.processed_event_count = len(events)
        if active.anchor_elapsed_seconds is not None:
            current_student_seconds = max(
                0.0,
                float(capture["elapsed_seconds"])
                - active.anchor_elapsed_seconds,
            )
            self._mark_missed_until(active, current_student_seconds)
        else:
            current_student_seconds = 0.0
        return {
            "capture": capture,
            "student_seconds": round(current_student_seconds, 3),
        }

    def status(self, lesson_id: str) -> dict[str, Any]:
        with self.lock:
            if self.active is None or self.active.lesson_id != lesson_id:
                return {"state": "idle"}
            active = self.active
            refreshed = self._refresh(active)
            if active.anchor_elapsed_seconds is None:
                state = "waiting_for_play"
            elif active.current_index >= len(active.steps):
                state = "guidance_complete"
            else:
                state = "guiding"
            current = (
                active.steps[active.current_index]
                if active.current_index < len(active.steps)
                else None
            )
            following = (
                active.steps[active.current_index + 1]
                if active.current_index + 1 < len(active.steps)
                else None
            )
            return {
                "state": state,
                "take_id": active.take.id,
                "current": current,
                "next": following,
                "student_seconds": refreshed["student_seconds"],
                "seconds_until_current": (
                    round(
                        float(current["reference_seconds"])
                        - refreshed["student_seconds"],
                        1,
                    )
                    if current
                    else None
                ),
                "completed_count": sum(
                    outcome["status"] == "completed"
                    for outcome in active.outcomes
                ),
                "missed_count": sum(
                    outcome["status"] == "missed" for outcome in active.outcomes
                ),
                "total_steps": len(active.steps),
                "event_count": len(refreshed["capture"]["events"]),
            }

    def stop(self, lesson_id: str) -> Take:
        with self.lock:
            if self.active is None or self.active.lesson_id != lesson_id:
                raise RuntimeError("Esta lección no tiene un intento activo.")
            active = self.active
            self._refresh(active)
            while active.current_index < len(active.steps):
                step = active.steps[active.current_index]
                active.outcomes.append(
                    {
                        "step_id": step["id"],
                        "status": "not_attempted",
                        "timing": None,
                        "student_seconds": None,
                        "delta_seconds": None,
                    }
                )
                active.current_index += 1

            result = self.runtime.finish_take_capture(active.checkpoint)
            active.take.ended_at = _timestamp_now()
            active.take.duration_seconds = round(
                time.monotonic() - active.started_monotonic, 3
            )
            active.take.events = result["events"]
            active.take.final_state = result["final_state"]
            completed = sum(
                outcome["status"] == "completed"
                for outcome in active.outcomes
            )
            active.take.features = {
                "schema_version": GUIDANCE_SCHEMA_VERSION,
                "mode": "guided",
                "steps": active.steps,
                "outcomes": active.outcomes,
                "completed_count": completed,
                "total_steps": len(active.steps),
                "score_percentage": round(
                    completed / len(active.steps) * 100
                ),
            }
            self.attempt_repository.save(active.take)
            self.active = None
            return active.take
