"""Convierte la técnica aprobada en consignas progresivas para el alumno."""

from __future__ import annotations

from typing import Any


GUIDANCE_SCHEMA_VERSION = 1
GESTURE_MINIMUM_CHANGE = 8
VALUE_TOLERANCE = 12

CONTROL_NAMES = {
    "low": "LOW",
    "mid": "MID",
    "high": "HIGH",
    "gain": "GAIN",
    "fx_adjust": "FX / FILTER",
    "volume": "VOLUME",
    "crossfader": "CROSSFADER",
    "play": "PLAY",
    "transport_cue": "CUE",
    "loop_active": "LOOP",
    "sync": "SYNC",
    "fx_on": "FX ON",
    "cue": "MONITOR CUE",
}


def _deck_name(section: str) -> str:
    return {"deck_a": "Deck A", "deck_b": "Deck B", "mixer": "Mixer"}.get(
        section, section
    )


def _gesture_instruction(event: dict[str, Any]) -> str:
    section = str(event["section"])
    control = str(event["control"])
    target = int(event["end_value"])
    name = CONTROL_NAMES.get(control, control.upper())
    if control == "crossfader":
        if target <= 24:
            return "Llevá el CROSSFADER hacia Deck A"
        if target >= 103:
            return "Llevá el CROSSFADER hacia Deck B"
        return "Llevá el CROSSFADER hacia el centro"
    if target <= 12:
        verb = "Cerrá"
    elif target >= 115:
        verb = "Abrí"
    elif event.get("direction") == "increase":
        verb = "Subí"
    elif event.get("direction") == "decrease":
        verb = "Bajá"
    else:
        verb = "Mové"
    return f"{verb} {name} de {_deck_name(section)}"


def build_guidance_steps(features: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = list(features.get("timeline", []))
    anchor = next(
        (
            event
            for event in timeline
            if event.get("type") == "transport_change"
            and event.get("section") == "deck_a"
            and event.get("control") == "play"
            and event.get("active")
        ),
        None,
    )
    if anchor is None:
        raise ValueError("La referencia no contiene un PLAY inicial de Deck A.")
    anchor_time = float(anchor["elapsed_seconds"])

    steps: list[dict[str, Any]] = []
    for event in timeline:
        event_type = event.get("type")
        event_time = float(event.get("elapsed_seconds", 0.0))
        if event_time < anchor_time or event is anchor:
            continue
        if event_type == "control_gesture":
            change = max(
                abs(int(event.get("delta", 0))),
                int(event.get("maximum_value", 0))
                - int(event.get("minimum_value", 0)),
            )
            if change < GESTURE_MINIMUM_CHANGE:
                continue
            step = {
                "kind": "control",
                "section": event["section"],
                "control": event["control"],
                "target_value": int(event["end_value"]),
                "instruction": _gesture_instruction(event),
            }
        elif event_type == "transport_change":
            if event.get("control") in {"loaded", "track_end"}:
                continue
            active = bool(event.get("active"))
            control_name = CONTROL_NAMES.get(
                str(event["control"]), str(event["control"]).upper()
            )
            step = {
                "kind": "transport",
                "section": event["section"],
                "control": event["control"],
                "target_active": active,
                "instruction": (
                    f'{"Activá" if active else "Desactivá"} {control_name} '
                    f'de {_deck_name(str(event["section"]))}'
                ),
            }
        else:
            continue
        step.update(
            {
                "id": f"step_{len(steps) + 1:03d}",
                "order": len(steps) + 1,
                "reference_seconds": round(event_time - anchor_time, 3),
            }
        )
        steps.append(step)
    return steps


def event_matches_step(event: dict[str, Any], step: dict[str, Any]) -> bool:
    if event.get("type") != "midi_change":
        return False
    if event.get("section") != step["section"]:
        return False
    if event.get("control") != step["control"]:
        return False
    value = int(event.get("value", 0))
    if step["kind"] == "transport":
        return (value >= 64) == bool(step["target_active"])
    target = int(step["target_value"])
    if target <= 12:
        return value <= 20
    if target >= 115:
        return value >= 107
    return abs(value - target) <= VALUE_TOLERANCE
