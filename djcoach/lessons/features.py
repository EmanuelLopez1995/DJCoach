"""Extracción determinista de una técnica desde una toma MIDI."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from djcoach.domain import Take


FEATURE_SCHEMA_VERSION = 2
GESTURE_GAP_SECONDS = 2.0
TIMING_CONTROLS = {"phase", "beat_phase", "track_progress"}
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
        if control in TIMING_CONTROLS or control in TRANSPORT_CONTROLS:
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

    transport_events = [
        {
            "type": "transport_change",
            "section": event.get("section"),
            "control": event.get("control"),
            "elapsed_seconds": _elapsed(event),
            "value": int(event.get("value", 0)),
            "active": int(event.get("value", 0)) >= 64,
        }
        for event in midi_events
        if event.get("control") in TRANSPORT_CONTROLS
    ]
    gestures = _extract_gestures(midi_events)
    timeline: list[dict[str, Any]] = [
        {**gesture, "elapsed_seconds": gesture["started_at"]}
        for gesture in gestures
    ]
    timeline.extend(transport_events)
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
        "timeline": timeline,
    }
