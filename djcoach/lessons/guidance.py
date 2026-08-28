"""Convierte la técnica aprobada en consignas progresivas para el alumno."""

from __future__ import annotations

from typing import Any

from djcoach.midi import format_loop_size


GUIDANCE_SCHEMA_VERSION = 4
GESTURE_MINIMUM_CHANGE = 8
VALUE_TOLERANCE = 12
SIMULTANEOUS_WINDOW_SECONDS = 2.5

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
    "loop_size": "TAMAÑO DE LOOP",
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
                # La duración viene de los mensajes MIDI reales del profesor:
                # permite enseñar un gesto progresivo, no sólo su destino.
                "duration_seconds": max(
                    0.0, round(float(event.get("duration_seconds", 0.0)), 3)
                ),
                "start_value": int(event.get("start_value", event["end_value"])),
            }
        elif event_type == "transport_change":
            if event.get("control") in {"loaded", "track_end"}:
                continue
            active = bool(event.get("active"))
            control_name = CONTROL_NAMES.get(
                str(event["control"]), str(event["control"]).upper()
            )
            instruction = (
                f'{"Activá" if active else "Desactivá"} {control_name} '
                f'de {_deck_name(str(event["section"]))}'
            )
            if (
                event.get("control") == "loop_active"
                and active
                and event.get("loop_size_midi") is not None
            ):
                instruction = (
                    f'Activá LOOP de {format_loop_size(int(event["loop_size_midi"]))} '
                    f'en {_deck_name(str(event["section"]))}'
                )
            step = {
                "kind": "transport",
                "section": event["section"],
                "control": event["control"],
                "target_active": active,
                "instruction": instruction,
                "duration_seconds": 0.0,
            }
        elif event_type == "selector_change":
            target = int(event["value"])
            step = {
                "kind": "selector",
                "section": event["section"],
                "control": "loop_size",
                "target_value": target,
                "instruction": (
                    f"Seleccioná un LOOP de {format_loop_size(target)} "
                    f"en {_deck_name(str(event['section']))}"
                ),
                "duration_seconds": 0.0,
            }
        else:
            continue
        step.update(
            {
                "id": f"step_{len(steps) + 1:03d}",
                "order": len(steps) + 1,
                "reference_seconds": round(event_time - anchor_time, 3),
                # No altera el flujo actual: sólo deja preparado el dato para
                # que una futura versión pueda tratar PLAY/LOOP como
                # prerrequisitos de recuperación.
                "is_critical": str(step["control"]) in {"play", "loop_active"},
            }
        )
        steps.append(step)
    return steps


def build_guidance_moments(
    steps: list[dict[str, Any]],
    window_seconds: float = SIMULTANEOUS_WINDOW_SECONDS,
) -> list[dict[str, Any]]:
    """Agrupa acciones cercanas sin crear relojes independientes por deck."""
    moments: list[dict[str, Any]] = []
    for step in sorted(steps, key=lambda item: item["reference_seconds"]):
        if (
            not moments
            or float(step["reference_seconds"])
            - float(moments[-1]["reference_seconds"])
            > window_seconds
            # La guía representa movimientos físicos: como máximo dos
            # controles simultáneos, uno por mano. Un tercer evento cercano
            # abre el siguiente micro-momento en lugar de quedar oculto.
            or len(moments[-1]["actions"]) >= 2
        ):
            moments.append(
                {
                    "id": f"moment_{len(moments) + 1:03d}",
                    "order": len(moments) + 1,
                    "reference_seconds": step["reference_seconds"],
                    "actions": [step],
                    "duration_seconds": float(step.get("duration_seconds", 0.0)),
                }
            )
        else:
            moments[-1]["actions"].append(step)
            moments[-1]["duration_seconds"] = max(
                float(moments[-1].get("duration_seconds", 0.0)),
                float(step.get("duration_seconds", 0.0)),
            )
    return moments


def event_matches_step(event: dict[str, Any], step: dict[str, Any]) -> bool:
    if event.get("type") != "midi_change":
        return False
    if event.get("section") != step["section"]:
        return False
    if event.get("control") != step["control"]:
        return False
    value = int(event.get("value", 0))
    if step["kind"] == "transport":
        return (value > 0) == bool(step["target_active"])
    target = int(step["target_value"])
    if step["kind"] == "selector":
        return abs(value - target) <= 5
    if target <= 12:
        return value <= 20
    if target >= 115:
        return value >= 107
    return abs(value - target) <= VALUE_TOLERANCE
