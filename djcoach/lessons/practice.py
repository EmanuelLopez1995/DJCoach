"""Grabación y seguimiento en vivo de una práctica guiada."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from djcoach.domain import Take, TakeRole

from .attempt_repository import AttemptRepository
from .guidance import (
    GUIDANCE_SCHEMA_VERSION,
    build_guidance_moments,
    build_guidance_steps,
    event_matches_step,
)
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
    moments: list[dict[str, Any]]
    started_monotonic: float
    processed_event_count: int = 0
    anchor_elapsed_seconds: float | None = None
    current_moment_index: int = 0
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
            moments = build_guidance_moments(steps)

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
                moments=moments,
                started_monotonic=time.monotonic(),
            )
            return take

    @staticmethod
    def _outcome_ids(active: ActiveStudentAttempt) -> set[str]:
        return {str(outcome["step_id"]) for outcome in active.outcomes}

    def _advance_resolved_moments(self, active: ActiveStudentAttempt) -> None:
        outcome_ids = self._outcome_ids(active)
        while active.current_moment_index < len(active.moments):
            moment = active.moments[active.current_moment_index]
            if not all(action["id"] in outcome_ids for action in moment["actions"]):
                break
            active.current_moment_index += 1

    def _record_outcome(
        self,
        active: ActiveStudentAttempt,
        step: dict[str, Any],
        status: str,
        timing: str | None = None,
        student_seconds: float | None = None,
        delta_seconds: float | None = None,
    ) -> None:
        if step["id"] in self._outcome_ids(active):
            return
        active.outcomes.append(
            {
                "step_id": step["id"],
                "status": status,
                "timing": timing,
                "student_seconds": student_seconds,
                "delta_seconds": delta_seconds,
            }
        )

    def _mark_missed_until(
        self, active: ActiveStudentAttempt, student_seconds: float
    ) -> None:
        self._advance_resolved_moments(active)
        while active.current_moment_index < len(active.moments):
            moment = active.moments[active.current_moment_index]
            if student_seconds <= moment["reference_seconds"] + MISSED_AFTER_SECONDS:
                break
            outcome_ids = self._outcome_ids(active)
            for action in moment["actions"]:
                if action["id"] not in outcome_ids:
                    self._record_outcome(active, action, "missed")
            active.current_moment_index += 1
            self._advance_resolved_moments(active)

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
            if active.current_moment_index >= len(active.moments):
                continue
            outcome_ids = self._outcome_ids(active)
            matched_step = next(
                (
                    action
                    for moment in active.moments[active.current_moment_index :]
                    if moment["reference_seconds"]
                    <= student_seconds + EARLY_ACTION_WINDOW_SECONDS
                    for action in moment["actions"]
                    if action["id"] not in outcome_ids
                    and event_matches_step(event, action)
                ),
                None,
            )
            if matched_step is not None:
                delta = round(
                    student_seconds - matched_step["reference_seconds"], 3
                )
                if delta < -ON_TIME_TOLERANCE_SECONDS:
                    timing = "early"
                elif delta > ON_TIME_TOLERANCE_SECONDS:
                    timing = "late"
                else:
                    timing = "on_time"
                self._record_outcome(
                    active,
                    matched_step,
                    "completed",
                    timing,
                    round(student_seconds, 3),
                    delta,
                )
                self._advance_resolved_moments(active)

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
            elif active.current_moment_index >= len(active.moments):
                state = "guidance_complete"
            else:
                state = "guiding"
            current = (
                active.moments[active.current_moment_index]
                if active.current_moment_index < len(active.moments)
                else None
            )
            following = (
                active.moments[active.current_moment_index + 1]
                if active.current_moment_index + 1 < len(active.moments)
                else None
            )
            previous_index = (
                active.current_moment_index - 1
                if active.current_moment_index > 0
                else None
            )
            previous = (
                active.moments[previous_index]
                if previous_index is not None
                else None
            )
            outcomes_by_id = {
                outcome["step_id"]: outcome for outcome in active.outcomes
            }

            def present(moment: dict[str, Any] | None) -> dict[str, Any] | None:
                if moment is None:
                    return None
                return {
                    **moment,
                    "actions": [
                        {
                            **action,
                            "outcome": outcomes_by_id.get(action["id"]),
                        }
                        for action in moment["actions"]
                    ],
                }

            return {
                "state": state,
                "take_id": active.take.id,
                "previous": present(previous),
                "current": present(current),
                "next": present(following),
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
            outcome_ids = self._outcome_ids(active)
            for step in active.steps:
                if step["id"] not in outcome_ids:
                    self._record_outcome(active, step, "not_attempted")

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
                "moments": active.moments,
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
