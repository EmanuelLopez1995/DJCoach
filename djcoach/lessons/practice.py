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
from .initial_state import compare_initial_state


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
            initial_comparison = compare_initial_state(
                reference.initial_state, snapshot
            )
            if not initial_comparison.ready:
                raise RuntimeError(
                    f"El mixer todavía tiene {initial_comparison.mismatch_count} "
                    "controles fuera del estado inicial del profesor."
                )

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
        outcome = {
            "step_id": step["id"],
            "status": status,
            "timing": timing,
            "student_seconds": student_seconds,
            "delta_seconds": delta_seconds,
        }
        for index, existing in enumerate(active.outcomes):
            if existing["step_id"] != step["id"]:
                continue
            # MISSED describe que el alumno no llegó a tiempo, pero no debe
            # impedir reconocer que finalmente realizó la acción correcta.
            if existing["status"] == "missed" and status == "completed":
                active.outcomes[index] = outcome
            return
        active.outcomes.append(outcome)

    @staticmethod
    def _recoverable_missed_step(
        active: ActiveStudentAttempt, event: dict[str, Any]
    ) -> dict[str, Any] | None:
        missed_ids = {
            str(outcome["step_id"])
            for outcome in active.outcomes
            if outcome["status"] == "missed"
        }
        return next(
            (
                step
                for step in reversed(active.steps)
                if step["id"] in missed_ids and event_matches_step(event, step)
            ),
            None,
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
            if matched_step is None:
                matched_step = self._recoverable_missed_step(active, event)
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
            steps_by_id = {step["id"]: step for step in active.steps}

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

            timeline = []
            for index, moment in enumerate(active.moments):
                shown = present(moment)
                moment_outcomes = [
                    outcomes_by_id.get(action["id"])
                    for action in moment["actions"]
                ]
                if any(
                    outcome and outcome["status"] == "missed"
                    for outcome in moment_outcomes
                ):
                    visual_state = "problem"
                elif all(moment_outcomes):
                    visual_state = "completed"
                elif index == active.current_moment_index:
                    visual_state = "current"
                else:
                    visual_state = "pending"
                timeline.append({**shown, "visual_state": visual_state})

            final_state = refreshed["capture"].get("final_state", {})
            rhythm = final_state.get("deck_tempos", {}).get("a", {})
            clock = final_state.get("midi_clock", {})
            bpm = clock.get("bpm") if clock.get("received") else None

            feedback = []
            for outcome in reversed(active.outcomes[-4:]):
                step = steps_by_id[str(outcome["step_id"])]
                timing = outcome.get("timing")
                delta_seconds = outcome.get("delta_seconds")
                delta_beats = (
                    round(float(delta_seconds) * float(bpm) / 60.0, 1)
                    if delta_seconds is not None and bpm is not None
                    else None
                )
                if outcome["status"] == "missed":
                    feedback_state = "problem"
                    verdict = "MISSED"
                    message = step["instruction"]
                elif timing == "early":
                    feedback_state = "warning"
                    verdict = "EARLY"
                    message = step["instruction"]
                elif timing == "late":
                    feedback_state = "warning"
                    verdict = "LATE"
                    message = step["instruction"]
                else:
                    feedback_state = "success"
                    verdict = (
                        "PERFECT"
                        if delta_beats is not None and abs(delta_beats) <= 0.5
                        else "GOOD"
                    )
                    message = step["instruction"]
                feedback.append(
                    {
                        "state": feedback_state,
                        "verdict": verdict,
                        "message": message,
                        "delta_beats": delta_beats,
                    }
                )

            combo = 0
            for outcome in reversed(active.outcomes):
                if outcome["status"] != "completed" or outcome.get("timing") in {
                    "early",
                    "late",
                }:
                    break
                combo += 1

            return {
                "state": state,
                "take_id": active.take.id,
                "previous": present(previous),
                "current": present(current),
                "next": present(following),
                "timeline": timeline,
                "feedback": feedback,
                "combo": combo,
                "mixer_state": {
                    "deck_a": final_state.get("deck_a", {}),
                    "deck_b": final_state.get("deck_b", {}),
                    "crossfader": final_state.get("crossfader", {}),
                },
                "current_moment_number": min(
                    active.current_moment_index + 1, len(active.moments)
                ),
                "total_moments": len(active.moments),
                "musical_context": {
                    "beat": rhythm.get("beat_in_bar")
                    if rhythm.get("downbeat_set")
                    else None,
                    "bar": rhythm.get("bar_count")
                    if rhythm.get("downbeat_set")
                    else None,
                    "bpm": round(float(bpm), 1) if bpm is not None else None,
                },
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
                "seconds_until_next": (
                    round(
                        float(following["reference_seconds"])
                        - refreshed["student_seconds"],
                        1,
                    )
                    if following
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
