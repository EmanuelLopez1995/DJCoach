"""Evaluación legible de un intento guiado del alumno.

La comparación es deliberadamente determinista: usa las acciones que ya fueron
reconocidas por la práctica guiada y conserva el detalle para una futura
comparación de curvas MIDI más precisa.
"""

from __future__ import annotations

from typing import Any


EVALUATION_SCHEMA_VERSION = 1


def _bpm_from_state(final_state: dict[str, Any]) -> float | None:
    clock = final_state.get("midi_clock", {})
    if not isinstance(clock, dict) or not clock.get("received"):
        return None
    value = clock.get("bpm")
    return float(value) if value is not None else None


def _timing_grade(
    outcome: dict[str, Any], bpm: float | None
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
    if magnitude <= 0.25:
        return "PERFECT", "success", 100, delta_beats
    if magnitude <= 1.0:
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
        verdict, state, quality, delta_beats = _timing_grade(outcome, bpm)
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
