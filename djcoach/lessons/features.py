"""Extracción determinista de una técnica desde una toma MIDI."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from djcoach.domain import Take
from djcoach.midi import format_loop_size


FEATURE_SCHEMA_VERSION = 3
GESTURE_GAP_SECONDS = 2.0
TIMING_CONTROLS = {"phase", "beat_phase", "track_progress"}
SELECTOR_CONTROLS = {"loop_size"}
LOOP_ACTIVATION_SIZE_WINDOW_SECONDS = 0.25
TRANSPORT_CONTROLS = {
    "loaded",
    "play",
    "transport_cue",
    "loop_active",
    "sync",
    "fx_on",
    "cue",
    "track_end",
}


def _elapsed(event: dict[str, Any]) -> float:
    return round(float(event.get("elapsed_seconds", 0.0)), 3)


def _gesture(events: list[dict[str, Any]]) -> dict[str, Any]:
    first = events[0]
    last = events[-1]
    values = [int(event["value"]) for event in events]
    delta = values[-1] - values[0]
    if delta > 1:
        direction = "increase"
    elif delta < -1:
        direction = "decrease"
    else:
        direction = "movement"
    return {
        "type": "control_gesture",
        "section": first["section"],
        "control": first["control"],
        "started_at": _elapsed(first),
        "ended_at": _elapsed(last),
        "duration_seconds": round(_elapsed(last) - _elapsed(first), 3),
        "start_value": values[0],
        "end_value": values[-1],
        "minimum_value": min(values),
        "maximum_value": max(values),
        "delta": delta,
        "direction": direction,
        "event_count": len(events),
    }


def _extract_gestures(midi_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in midi_events:
        control = str(event.get("control", ""))
        if (
            control in TIMING_CONTROLS
            or control in TRANSPORT_CONTROLS
            or control in SELECTOR_CONTROLS
        ):
            continue
        if event.get("value") is None:
            continue
        grouped[(str(event.get("section", "")), control)].append(event)

    gestures: list[dict[str, Any]] = []
    for events in grouped.values():
        events.sort(key=_elapsed)
        current: list[dict[str, Any]] = []
        for event in events:
            if current and _elapsed(event) - _elapsed(current[-1]) > GESTURE_GAP_SECONDS:
                gestures.append(_gesture(current))
                current = []
            current.append(event)
        if current:
            gestures.append(_gesture(current))

    # Descarta ruido de un solo paso sin cambio apreciable.
    gestures = [
        gesture
        for gesture in gestures
        if gesture["event_count"] > 1 or abs(gesture["delta"]) > 1
    ]
    return sorted(gestures, key=lambda gesture: gesture["started_at"])


def extract_take_features(take: Take) -> dict[str, Any]:
    midi_events = [
        event for event in take.events if event.get("type") == "midi_change"
    ]
    transition_started = next(
        (
            event
            for event in take.events
            if event.get("type") == "transition_started"
        ),
        None,
    )
    transition_ended = next(
        (
            event
            for event in reversed(take.events)
            if event.get("type") == "transition_ended"
        ),
        None,
    )

    transition: dict[str, Any] | None = None
    if transition_started is not None:
        transition = {
            "started_at": _elapsed(transition_started),
            "ended_at": (
                _elapsed(transition_ended) if transition_ended else None
            ),
            "duration_seconds": (
                round(
                    _elapsed(transition_ended) - _elapsed(transition_started),
                    3,
                )
                if transition_ended
                else None
            ),
            "completed": transition_ended is not None,
        }

    activity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in midi_events:
        control = str(event.get("control", ""))
        if control not in TIMING_CONTROLS:
            activity[(str(event.get("section", "")), control)].append(event)

    controls_used = [
        {
            "section": section,
            "control": control,
            "event_count": len(events),
            "first_at": _elapsed(events[0]),
            "last_at": _elapsed(events[-1]),
        }
        for (section, control), events in activity.items()
    ]
    controls_used.sort(key=lambda item: item["first_at"])

    attached_loop_size_events: set[int] = set()

    def loop_size_at_activation(section: str, event_index: int) -> int | None:
        elapsed = _elapsed(midi_events[event_index])
        initial_deck = take.initial_state.get(section, {})
        initial_loop_size = initial_deck.get("loop_size", {})
        current = initial_loop_size.get("midi")
        for candidate in midi_events[:event_index]:
            if (
                candidate.get("section") == section
                and candidate.get("control") == "loop_size"
            ):
                current = candidate.get("value")

        # Traktor puede informar LOOP ON antes de actualizar el selector al
        # tamaño real de un loop almacenado. Una actualización inmediata forma
        # parte de la activación, no es una segunda acción del profesor.
        for candidate in midi_events[event_index + 1 :]:
            delay = _elapsed(candidate) - elapsed
            if delay > LOOP_ACTIVATION_SIZE_WINDOW_SECONDS:
                break
            if (
                candidate.get("section") == section
                and candidate.get("control") == "loop_size"
            ):
                current = candidate.get("value")
                attached_loop_size_events.add(id(candidate))
                break
        return int(current) if current is not None else None

    transport_events = []
    for event_index, event in enumerate(midi_events):
        if event.get("control") not in TRANSPORT_CONTROLS:
            continue
        transport_event = {
            "type": "transport_change",
            "section": event.get("section"),
            "control": event.get("control"),
            "elapsed_seconds": _elapsed(event),
            "value": int(event.get("value", 0)),
            "active": int(event.get("value", 0)) > 0,
        }
        if event.get("control") == "loop_active" and transport_event["active"]:
            loop_midi = loop_size_at_activation(
                str(event.get("section", "")), event_index
            )
            transport_event["loop_size_midi"] = loop_midi
            transport_event["loop_size_label"] = format_loop_size(loop_midi)
        transport_events.append(transport_event)

    selector_events = [
        {
            "type": "selector_change",
            "section": event.get("section"),
            "control": "loop_size",
            "elapsed_seconds": _elapsed(event),
            "value": int(event.get("value", 0)),
            "label": format_loop_size(int(event.get("value", 0))),
        }
        for event in midi_events
        if event.get("control") == "loop_size"
        and id(event) not in attached_loop_size_events
    ]
    gestures = _extract_gestures(midi_events)
    timeline: list[dict[str, Any]] = [
        {**gesture, "elapsed_seconds": gesture["started_at"]}
        for gesture in gestures
    ]
    timeline.extend(transport_events)
    timeline.extend(selector_events)
    if transition_started is not None:
        timeline.append(
            {
                "type": "transition_started",
                "elapsed_seconds": _elapsed(transition_started),
            }
        )
    if transition_ended is not None:
        timeline.append(
            {
                "type": "transition_ended",
                "elapsed_seconds": _elapsed(transition_ended),
            }
        )
    timeline.sort(key=lambda item: float(item["elapsed_seconds"]))

    meaningful_event_count = sum(
        event.get("control") not in TIMING_CONTROLS for event in midi_events
    )
    return {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "event_count": len(take.events),
        "midi_change_count": len(midi_events),
        "meaningful_event_count": meaningful_event_count,
        "transition": transition,
        "controls_used": controls_used,
        "gestures": gestures,
        "transport_events": transport_events,
        "selector_events": selector_events,
        "timeline": timeline,
    }
