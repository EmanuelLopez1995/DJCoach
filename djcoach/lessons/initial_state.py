"""Contrato de estado inicial compartido entre profesor y alumno."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MIDI_TOLERANCE = 4
TRACK_POSITION_TOLERANCE = 2
BPM_TOLERANCE = 0.6

CONTINUOUS_CONTROLS = (
    ("low", "LOW"),
    ("mid", "MID"),
    ("high", "HIGH"),
    ("gain", "GAIN"),
    ("fx_adjust", "FX / FILTER"),
    ("volume", "VOLUME"),
    ("track_progress", "POSICIÓN DEL TRACK"),
)
BOOLEAN_CONTROLS = (
    ("fx_on", "FX ON"),
    ("cue", "MONITOR CUE"),
    ("play", "PLAY"),
    ("loop_active", "LOOP"),
    ("sync", "SYNC"),
)


@dataclass(frozen=True)
class InitialStateItem:
    section: str
    control: str
    label: str
    kind: str
    target: int | float | bool | None
    current: int | float | bool | None
    target_received: bool
    current_received: bool
    matched: bool
    instruction: str

    @property
    def target_display(self) -> str:
        return _display(self.target, self.kind)

    @property
    def current_display(self) -> str:
        return _display(self.current, self.kind)


@dataclass(frozen=True)
class InitialStateComparison:
    items: tuple[InitialStateItem, ...]

    @property
    def ready(self) -> bool:
        return bool(self.items) and all(item.matched for item in self.items)

    @property
    def mismatch_count(self) -> int:
        return sum(not item.matched for item in self.items)


def _display(value: int | float | bool | None, kind: str) -> str:
    if value is None:
        return "---"
    if kind == "boolean":
        return "ON" if bool(value) else "OFF"
    if kind == "bpm":
        return f"{float(value):.1f} BPM"
    return f"MIDI {int(value)}"


def _instruction(
    label: str,
    kind: str,
    target: int | float | bool | None,
    current: int | float | bool | None,
    target_received: bool,
    current_received: bool,
) -> str:
    if not target_received or target is None:
        return "La referencia no guardó este valor"
    if not current_received or current is None:
        return f"Mové {label} para detectar su posición"
    if kind == "boolean":
        return f'{"Activá" if bool(target) else "Desactivá"} {label}'
    if float(current) < float(target):
        return f"Subí {label}"
    return f"Bajá {label}"


def _make_item(
    section: str,
    control: str,
    label: str,
    kind: str,
    target: int | float | bool | None,
    current: int | float | bool | None,
    target_received: bool,
    current_received: bool,
    tolerance: float = 0.0,
) -> InitialStateItem:
    if not target_received or not current_received:
        matched = False
    elif target is None or current is None:
        matched = False
    elif kind == "boolean":
        matched = bool(target) == bool(current)
    else:
        matched = abs(float(target) - float(current)) <= tolerance
    return InitialStateItem(
        section=section,
        control=control,
        label=label,
        kind=kind,
        target=target,
        current=current,
        target_received=target_received,
        current_received=current_received,
        matched=matched,
        instruction=(
            "Posición correcta"
            if matched
            else _instruction(
                label,
                kind,
                target,
                current,
                target_received,
                current_received,
            )
        ),
    )


def compare_initial_state(
    reference_state: dict[str, Any], current_state: dict[str, Any]
) -> InitialStateComparison:
    items: list[InitialStateItem] = []
    for section, deck_label in (("deck_a", "Deck A"), ("deck_b", "Deck B")):
        reference_deck = reference_state[section]
        current_deck = current_state[section]
        for control, label in CONTINUOUS_CONTROLS:
            reference_value = reference_deck[control]
            current_value = current_deck[control]
            tolerance = (
                TRACK_POSITION_TOLERANCE
                if control == "track_progress"
                else MIDI_TOLERANCE
            )
            items.append(
                _make_item(
                    section,
                    control,
                    f"{label} {deck_label}",
                    "midi",
                    reference_value.get("midi"),
                    current_value.get("midi"),
                    bool(reference_value.get("received")),
                    bool(current_value.get("received")),
                    tolerance,
                )
            )
        for control, label in BOOLEAN_CONTROLS:
            items.append(
                _make_item(
                    section,
                    control,
                    f"{label} {deck_label}",
                    "boolean",
                    reference_deck.get(control),
                    current_deck.get(control),
                    bool(reference_deck.get(f"{control}_received")),
                    bool(current_deck.get(f"{control}_received")),
                )
            )

    reference_crossfader = reference_state["crossfader"]
    current_crossfader = current_state["crossfader"]
    items.append(
        _make_item(
            "mixer",
            "crossfader",
            "CROSSFADER",
            "midi",
            reference_crossfader.get("midi"),
            current_crossfader.get("midi"),
            bool(reference_crossfader.get("received")),
            bool(current_crossfader.get("received")),
            MIDI_TOLERANCE,
        )
    )

    reference_clock = reference_state["midi_clock"]
    current_clock = current_state["midi_clock"]
    items.append(
        _make_item(
            "mixer",
            "master_clock",
            "MASTER CLOCK",
            "boolean",
            reference_clock.get("active"),
            current_clock.get("active"),
            bool(reference_clock.get("received")),
            bool(current_clock.get("received")),
        )
    )
    items.append(
        _make_item(
            "mixer",
            "master_bpm",
            "MASTER BPM",
            "bpm",
            reference_clock.get("bpm"),
            current_clock.get("bpm"),
            bool(reference_clock.get("received")),
            bool(current_clock.get("received")),
            BPM_TOLERANCE,
        )
    )
    return InitialStateComparison(tuple(items))
