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
from .evaluation import evaluate_guided_attempt


# Es una ventana breve de evaluación, no un bloqueo de la partitura. La guía
# visual ya avanza estrictamente por tiempo; al cerrarse esta ventana el fallo
# pasa a la cola secundaria MISSED.
MISSED_AFTER_SECONDS = 3.0
ON_TIME_TOLERANCE_SECONDS = 5.0
EARLY_ACTION_WINDOW_SECONDS = 10.0
CONTINUOUS_PREP_ALLOWANCE_SECONDS = 0.5


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

    @staticmethod
    def _step_target_seconds(step: dict[str, Any]) -> float:
        return float(
            step.get(
                "target_seconds",
                float(step["reference_seconds"])
                + float(step.get("duration_seconds", 0.0)),
            )
        )

    @staticmethod
    def _step_can_match_at(step: dict[str, Any], student_seconds: float) -> bool:
        """Evita que un valor de un gesto anterior complete uno futuro."""
        duration = float(step.get("duration_seconds", 0.0))
        if duration <= 0.0:
            return True
        return student_seconds >= (
            float(step["reference_seconds"])
            - CONTINUOUS_PREP_ALLOWANCE_SECONDS
        )

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
            return
        active.outcomes.append(outcome)

    def _mark_missed_until(
        self, active: ActiveStudentAttempt, student_seconds: float
    ) -> None:
        """Cierra ventanas vencidas sin tocar el reloj de la lección."""
        outcome_ids = self._outcome_ids(active)
        for moment in active.moments:
            for action in moment["actions"]:
                deadline = (
                    float(moment["reference_seconds"])
                    + float(action.get("duration_seconds", 0.0))
                    + MISSED_AFTER_SECONDS
                )
                if student_seconds <= deadline:
                    continue
                if action["id"] not in outcome_ids:
                    self._record_outcome(active, action, "missed")
                    outcome_ids.add(str(action["id"]))

    @staticmethod
    def _guidance_end_seconds(active: ActiveStudentAttempt) -> float:
        return max(
            float(moment["reference_seconds"])
            + max(
                float(action.get("duration_seconds", 0.0))
                for action in moment["actions"]
            )
            + MISSED_AFTER_SECONDS
            for moment in active.moments
        )

    @staticmethod
    def _scheduled_moment_index(
        active: ActiveStudentAttempt, student_seconds: float
    ) -> int | None:
        """Último momento cuyo instante musical ya llegó.

        Antes del primer evento se conserva ese primer momento para poder
        anunciarlo en PREPARATE. Después, el índice avanza sólo con el reloj,
        incluso cuando una acción anterior quedó MISSED.
        """
        if not active.moments:
            return None
        index = 0
        for candidate, moment in enumerate(active.moments):
            if float(moment["reference_seconds"]) > student_seconds:
                break
            index = candidate
        return index

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
            outcome_ids = self._outcome_ids(active)
            candidates = [
                step
                for step in active.steps
                if step["id"] not in outcome_ids
                and -EARLY_ACTION_WINDOW_SECONDS
                <= student_seconds - self._step_target_seconds(step)
                <= MISSED_AFTER_SECONDS
                and self._step_can_match_at(step, student_seconds)
                and event_matches_step(event, step)
            ]
            # Si el mismo control aparece varias veces, asociamos el gesto al
            # momento musical más cercano, no al primer paso pendiente.
            matched_step = min(
                candidates,
                key=lambda step: abs(
                    student_seconds - self._step_target_seconds(step)
                ),
                default=None,
            )
            if matched_step is not None:
                delta = round(
                    student_seconds - self._step_target_seconds(matched_step), 3
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
                scheduled_index = None
            else:
                scheduled_index = self._scheduled_moment_index(
                    active, refreshed["student_seconds"]
                )
            if active.anchor_elapsed_seconds is not None and (
                len(self._outcome_ids(active)) == len(active.steps)
                or scheduled_index is None
                or refreshed["student_seconds"]
                > self._guidance_end_seconds(active)
            ):
                state = "guidance_complete"
            elif active.anchor_elapsed_seconds is not None:
                state = "guiding"
            current = (
                active.moments[scheduled_index]
                if scheduled_index is not None
                else None
            )
            following = (
                active.moments[scheduled_index + 1]
                if scheduled_index is not None
                and scheduled_index + 1 < len(active.moments)
                else None
            )
            previous_index = (
                scheduled_index - 1
                if scheduled_index is not None and scheduled_index > 0
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
                moment_duration = max(
                    float(action.get("duration_seconds", 0.0))
                    for action in moment["actions"]
                )
                moment_started_at = float(moment["reference_seconds"])
                holding = (
                    moment_duration > 0.05
                    and moment_started_at
                    <= refreshed["student_seconds"]
                    < moment_started_at + moment_duration
                )
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
                elif index == scheduled_index:
                    visual_state = "current"
                elif float(moment["reference_seconds"]) < refreshed["student_seconds"]:
                    visual_state = "past"
                else:
                    visual_state = "pending"
                timeline.append(
                    {
                        **shown,
                        "visual_state": visual_state,
                        "holding": holding,
                        "hold_progress": (
                            round(
                                (refreshed["student_seconds"] - moment_started_at)
                                / moment_duration,
                                3,
                            )
                            if holding
                            else None
                        ),
                    }
                )

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
                # Durante la mezcla el feedback debe sentirse musical. La
                # evaluación persistida conserva sus tiempos en segundos,
                # pero la pantalla responde en beats cuando Traktor informa
                # el BPM actual.
                elif delta_beats is not None and delta_beats <= -1.5:
                    feedback_state = "warning"
                    verdict = "EARLY"
                    message = step["instruction"]
                elif delta_beats is not None and delta_beats >= 1.5:
                    feedback_state = "warning"
                    verdict = "LATE"
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
                "after_next": present(
                    active.moments[scheduled_index + 2]
                    if scheduled_index is not None
                    and scheduled_index + 2 < len(active.moments)
                    else None
                ),
                "timeline": timeline,
                "missed": [
                    {**steps_by_id[str(outcome["step_id"])], "outcome": outcome}
                    for outcome in active.outcomes
                    if outcome["status"] == "missed"
                ],
                "feedback": feedback,
                "combo": combo,
                "mixer_state": {
                    "deck_a": final_state.get("deck_a", {}),
                    "deck_b": final_state.get("deck_b", {}),
                    "crossfader": final_state.get("crossfader", {}),
                },
                "current_moment_number": min(
                    (scheduled_index or 0) + 1, len(active.moments)
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
            active.take.features["evaluation"] = evaluate_guided_attempt(
                active.steps,
                active.outcomes,
                result["final_state"],
                result["events"],
                active.anchor_elapsed_seconds,
            )
            self.attempt_repository.save(active.take)
            self.active = None
            return active.take
