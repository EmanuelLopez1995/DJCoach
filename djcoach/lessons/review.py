"""EdiciÃ³n manual, persistible y no destructiva de una referencia docente."""

from __future__ import annotations

import copy
from typing import Any


PHASES = ("Sin fase", "Entrada", "EQ Prep", "Blend", "Bass Swap", "FX", "Salida")


def prepare_review_timeline(features: dict[str, Any]) -> list[dict[str, Any]]:
    """Asigna IDs estables a la timeline editable y conserva el orden musical."""
    timeline = features.setdefault("timeline", [])
    for index, event in enumerate(timeline, start=1):
        event.setdefault("review_id", f"event_{index:03d}")
        event.setdefault("phase", "Sin fase")
    timeline.sort(key=lambda item: float(item.get("elapsed_seconds", 0.0)))
    return timeline


def _refresh_views(features: dict[str, Any]) -> None:
    timeline = prepare_review_timeline(features)
    features["gestures"] = [
        event for event in timeline if event.get("type") == "control_gesture"
    ]
    features["transport_events"] = [
        event for event in timeline if event.get("type") == "transport_change"
    ]
    features["selector_events"] = [
        event for event in timeline if event.get("type") == "selector_change"
    ]


def delete_event(features: dict[str, Any], review_id: str) -> bool:
    timeline = prepare_review_timeline(features)
    remaining = [event for event in timeline if event.get("review_id") != review_id]
    if len(remaining) == len(timeline):
        return False
    features["timeline"] = remaining
    _refresh_views(features)
    return True


def set_event_phase(features: dict[str, Any], review_id: str, phase: str) -> bool:
    if phase not in PHASES:
        raise ValueError("Fase no vÃ¡lida.")
    for event in prepare_review_timeline(features):
        if event.get("review_id") == review_id:
            event["phase"] = phase
            return True
    return False


def summarize_phases(features: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve las fases editoriales en su orden musical, con sus acciones."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in prepare_review_timeline(features):
        phase = str(event.get("phase", "Sin fase"))
        grouped.setdefault(phase, []).append(event)
    return [
        {"phase": phase, "events": events}
        for phase, events in grouped.items()
    ]


def publish_validation_errors(features: dict[str, Any]) -> list[str]:
    """Reglas mínimas para no publicar una referencia imposible de practicar."""
    timeline = prepare_review_timeline(features)
    if not timeline:
        return ["La referencia no tiene acciones para enseñar."]
    has_anchor = any(
        event.get("type") == "transport_change"
        and event.get("section") == "deck_a"
        and event.get("control") == "play"
        and event.get("active")
        for event in timeline
    )
    if not has_anchor:
        return ["Falta el PLAY inicial de Deck A que inicia el reloj de práctica."]
    actionable = [
        event for event in timeline
        if event.get("type") in {"control_gesture", "transport_change", "selector_change"}
    ]
    if not actionable:
        return ["No quedaron acciones MIDI practicables después de la edición."]
    if not any(event.get("phase") not in {None, "Sin fase"} for event in actionable):
        return ["Asigná al menos una fase (Entrada, EQ Prep, Blend, Bass Swap, FX o Salida)."]
    return []


def _interpolate(points: list[dict[str, Any]], offset: float) -> int:
    ordered = sorted(points, key=lambda point: float(point["offset_seconds"]))
    if offset <= float(ordered[0]["offset_seconds"]):
        return int(ordered[0]["value"])
    for left, right in zip(ordered, ordered[1:]):
        left_time = float(left["offset_seconds"])
        right_time = float(right["offset_seconds"])
        if offset <= right_time:
            progress = (offset - left_time) / max(0.001, right_time - left_time)
            return round(int(left["value"]) + (int(right["value"]) - int(left["value"])) * progress)
    return int(ordered[-1]["value"])


def split_gesture(features: dict[str, Any], review_id: str) -> bool:
    timeline = prepare_review_timeline(features)
    index = next((i for i, event in enumerate(timeline) if event.get("review_id") == review_id), None)
    if index is None:
        return False
    original = timeline[index]
    duration = float(original.get("duration_seconds", 0.0))
    if original.get("type") != "control_gesture" or duration < 0.4:
        return False
    midpoint = round(duration / 2, 3)
    trajectory = list(original.get("trajectory", [])) or [
        {"offset_seconds": 0.0, "value": int(original["start_value"])},
        {"offset_seconds": duration, "value": int(original["end_value"])},
    ]
    midpoint_value = _interpolate(trajectory, midpoint)
    left_points = [point for point in trajectory if float(point["offset_seconds"]) < midpoint]
    right_points = [point for point in trajectory if float(point["offset_seconds"]) > midpoint]
    left_points.append({"offset_seconds": midpoint, "value": midpoint_value})
    right_points.insert(0, {"offset_seconds": 0.0, "value": midpoint_value})
    right_points = [
        {"offset_seconds": round(float(point["offset_seconds"]) - midpoint, 3), "value": int(point["value"])}
        for point in right_points
        if float(point["offset_seconds"]) >= midpoint
    ]
    right_points.insert(0, {"offset_seconds": 0.0, "value": midpoint_value}) if not right_points or right_points[0]["offset_seconds"] != 0.0 else None

    def build(points: list[dict[str, Any]], start_value: int, end_value: int, start_at: float, gesture_duration: float, suffix: str) -> dict[str, Any]:
        event = copy.deepcopy(original)
        event.update(
            {
                "review_id": f"{review_id}_{suffix}",
                "elapsed_seconds": round(start_at, 3),
                "started_at": round(start_at, 3),
                "ended_at": round(start_at + gesture_duration, 3),
                "duration_seconds": round(gesture_duration, 3),
                "start_value": start_value,
                "end_value": end_value,
                "minimum_value": min(point["value"] for point in points),
                "maximum_value": max(point["value"] for point in points),
                "delta": end_value - start_value,
                "direction": "increase" if end_value > start_value else "decrease" if end_value < start_value else "movement",
                "trajectory": points,
            }
        )
        return event

    start_at = float(original.get("started_at", original["elapsed_seconds"]))
    left = build(left_points, int(original["start_value"]), midpoint_value, start_at, midpoint, "a")
    right = build(right_points, midpoint_value, int(original["end_value"]), start_at + midpoint, duration - midpoint, "b")
    timeline[index : index + 1] = [left, right]
    _refresh_views(features)
    return True


def merge_with_next(features: dict[str, Any], review_id: str) -> bool:
    timeline = prepare_review_timeline(features)
    index = next((i for i, event in enumerate(timeline) if event.get("review_id") == review_id), None)
    if index is None or index + 1 >= len(timeline):
        return False
    first, second = timeline[index], timeline[index + 1]
    if not (
        first.get("type") == second.get("type") == "control_gesture"
        and first.get("section") == second.get("section")
        and first.get("control") == second.get("control")
    ):
        return False
    merged = copy.deepcopy(first)
    start_at = float(first.get("started_at", first["elapsed_seconds"]))
    end_at = float(second.get("ended_at", second["elapsed_seconds"]))
    offset = float(second.get("started_at", second["elapsed_seconds"])) - start_at
    first_points = list(first.get("trajectory", []))
    second_points = [
        {"offset_seconds": round(offset + float(point["offset_seconds"]), 3), "value": int(point["value"])}
        for point in second.get("trajectory", [])
    ]
    points = first_points + second_points
    merged.update(
        {
            "review_id": f"{review_id}_merged",
            "elapsed_seconds": round(start_at, 3),
            "started_at": round(start_at, 3),
            "ended_at": round(end_at, 3),
            "duration_seconds": round(end_at - start_at, 3),
            "end_value": int(second["end_value"]),
            "minimum_value": min(int(first["minimum_value"]), int(second["minimum_value"])),
            "maximum_value": max(int(first["maximum_value"]), int(second["maximum_value"])),
            "delta": int(second["end_value"]) - int(first["start_value"]),
            "trajectory": points,
        }
    )
    merged["direction"] = "increase" if merged["delta"] > 0 else "decrease" if merged["delta"] < 0 else "movement"
    timeline[index : index + 2] = [merged]
    _refresh_views(features)
    return True
