"""Evaluación legible de un intento guiado del alumno.

La comparación es deliberadamente determinista: usa las acciones que ya fueron
reconocidas por la práctica guiada y conserva el detalle para una futura
comparación de curvas MIDI más precisa.
"""

from __future__ import annotations

from typing import Any


EVALUATION_SCHEMA_VERSION = 1
SUSTAINED_CURVE_TOLERANCE_MIDI = 12


def _bpm_from_state(final_state: dict[str, Any]) -> float | None:
    clock = final_state.get("midi_clock", {})
    if not isinstance(clock, dict) or not clock.get("received"):
        return None
    value = clock.get("bpm")
    return float(value) if value is not None else None


def _interpolate(points: list[tuple[float, int]], offset: float) -> float:
    if offset <= points[0][0]:
        return float(points[0][1])
    for (left_time, left_value), (right_time, right_value) in zip(
        points, points[1:]
    ):
        if offset <= right_time:
            if right_time == left_time:
                return float(right_value)
            progress = (offset - left_time) / (right_time - left_time)
            return left_value + (right_value - left_value) * progress
    return float(points[-1][1])


def _sustained_curve(
    step: dict[str, Any],
    student_events: list[dict[str, Any]] | None,
    student_anchor_seconds: float | None,
) -> dict[str, Any] | None:
    """Compara cuatro tramos del gesto dentro de una banda tolerante."""
    duration = float(step.get("duration_seconds", 0.0))
    if (
        step.get("kind") != "control"
        or duration < 1.0
        or not student_events
        or student_anchor_seconds is None
    ):
        return None

    raw_trajectory = list(step.get("trajectory", []))
    points = [
        (float(point["offset_seconds"]), int(point["value"]))
        for point in raw_trajectory
        if isinstance(point, dict)
        and point.get("offset_seconds") is not None
        and point.get("value") is not None
    ]
    if not points:
        points = [
            (0.0, int(step.get("start_value", step["target_value"]))),
            (duration, int(step["target_value"])),
        ]
    points.sort(key=lambda point: point[0])

    samples = sorted(
        (
            float(event.get("elapsed_seconds", 0.0)) - student_anchor_seconds,
            int(event["value"]),
        )
        for event in student_events
        if event.get("type") == "midi_change"
        and event.get("section") == step.get("section")
        and event.get("control") == step.get("control")
        and event.get("value") is not None
    )
    if not samples:
        return None

    reference_start = float(step["reference_seconds"])
    window = max(0.6, min(2.0, duration * 0.22))
    errors: list[float] = []
    for progress in (0.25, 0.5, 0.75, 1.0):
        expected_at = reference_start + duration * progress
        nearby = [
            sample
            for sample in samples
            if abs(sample[0] - expected_at) <= window
        ]
        if not nearby:
            continue
        student_value = min(nearby, key=lambda sample: abs(sample[0] - expected_at))[1]
        expected_value = _interpolate(points, duration * progress)
        errors.append(abs(student_value - expected_value))
    if not errors:
        return None
    average_error = round(sum(errors) / len(errors), 1)
    return {
        "sample_count": len(errors),
        "average_error_midi": average_error,
        "within_tolerance": average_error <= SUSTAINED_CURVE_TOLERANCE_MIDI,
    }


def _timing_grade(
    outcome: dict[str, Any],
    bpm: float | None,
    step: dict[str, Any],
    curve: dict[str, Any] | None = None,
) -> tuple[str, str, int, float | None]:
    """Devuelve veredicto, estado visual, calidad y diferencia en beats."""
    if outcome.get("status") != "completed":
        return "MISSED", "problem", 0, None
    delta_seconds = outcome.get("delta_seconds")
    if delta_seconds is None:
        return "GOOD", "success", 85, None
    delta = float(delta_seconds)
    delta_beats = round(delta * bpm / 60.0, 1) if bpm else None
    magnitude = abs(delta_beats) if delta_beats is not None else abs(delta)
    sustained = step.get("kind") == "control" and float(
        step.get("duration_seconds", 0.0)
    ) > 0.0
    perfect_tolerance = 1.0 if sustained else 0.25
    good_tolerance = (
        max(
            2.0,
            min(
                4.0,
                float(step.get("duration_seconds", 0.0))
                * float(bpm or 60.0)
                / 60.0
                * 0.35,
            ),
        )
        if sustained
        else 1.0
    )
    if sustained and curve and curve["within_tolerance"]:
        if magnitude <= perfect_tolerance and curve["average_error_midi"] <= 6:
            return "PERFECT", "success", 100, delta_beats
        return "GOOD", "success", 85, delta_beats
    if magnitude <= perfect_tolerance:
        return "PERFECT", "success", 100, delta_beats
    if magnitude <= good_tolerance:
        return "GOOD", "success", 85, delta_beats
    if delta < 0:
        return "EARLY", "warning", 65, delta_beats
    return "LATE", "warning", 65, delta_beats


def _feedback_for(verdict: str, instruction: str, delta_beats: float | None) -> str:
    if verdict == "PERFECT":
        return "Timing muy preciso."
    if verdict == "GOOD":
        return "Acción correcta; mantené esa referencia."
    if verdict == "EARLY":
        detail = f" {abs(delta_beats):g} beats antes." if delta_beats is not None else ""
        return f"Esperá un poco más antes de: {instruction}.{detail}"
    if verdict == "LATE":
        detail = f" {abs(delta_beats):g} beats tarde." if delta_beats is not None else ""
        return f"Prepará la mano antes para: {instruction}.{detail}"
    return f"No se realizó a tiempo: {instruction}."


def evaluate_guided_attempt(
    steps: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    final_state: dict[str, Any] | None = None,
    student_events: list[dict[str, Any]] | None = None,
    student_anchor_seconds: float | None = None,
) -> dict[str, Any]:
    """Resume una práctica en resultados por acción y recomendaciones."""
    final_state = final_state or {}
    bpm = _bpm_from_state(final_state)
    outcomes_by_id = {str(item["step_id"]): item for item in outcomes}
    results: list[dict[str, Any]] = []
    quality_values: list[int] = []
    groups: dict[str, list[int]] = {"mixer": [], "transport": []}

    for step in sorted(steps, key=lambda item: int(item.get("order", 0))):
        outcome = outcomes_by_id.get(str(step["id"]), {"status": "not_attempted"})
        curve = _sustained_curve(step, student_events, student_anchor_seconds)
        verdict, state, quality, delta_beats = _timing_grade(
            outcome, bpm, step, curve
        )
        category = "mixer" if step.get("kind") == "control" else "transport"
        quality_values.append(quality)
        groups[category].append(quality)
        results.append(
            {
                "step_id": step["id"],
                "instruction": step["instruction"],
                "category": category,
                "verdict": verdict,
                "state": state,
                "quality": quality,
                "delta_beats": delta_beats,
                "feedback": _feedback_for(verdict, step["instruction"], delta_beats),
                "curve": curve,
            }
        )

    completed_count = sum(item["verdict"] not in {"MISSED"} for item in results)
    missed = [item for item in results if item["verdict"] == "MISSED"]
    timing = [item for item in results if item["verdict"] in {"EARLY", "LATE"}]
    recommendations = [item["feedback"] for item in (missed + timing)[:3]]
    if not recommendations:
        recommendations = ["Muy buena ejecución: repetí la técnica para consolidarla."]
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "bpm": round(bpm, 1) if bpm is not None else None,
        "completion_percentage": round(completed_count / len(steps) * 100) if steps else 0,
        "quality_score": round(sum(quality_values) / len(quality_values)) if quality_values else 0,
        "completed_count": completed_count,
        "missed_count": len(missed),
        "timing_issue_count": len(timing),
        "by_category": {
            name: round(sum(values) / len(values)) if values else None
            for name, values in groups.items()
        },
        "results": results,
        "recommendations": recommendations,
    }
