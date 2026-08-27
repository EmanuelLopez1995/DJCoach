"""Reglas de preparación antes de grabar una referencia en Traktor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreparationStatus:
    midi_connected: bool
    deck_a_loaded: bool
    deck_b_loaded: bool
    deck_a_name_confirmed: bool
    deck_b_name_confirmed: bool

    @property
    def ready(self) -> bool:
        return all(
            (
                self.midi_connected,
                self.deck_a_loaded,
                self.deck_b_loaded,
                self.deck_a_name_confirmed,
                self.deck_b_name_confirmed,
            )
        )


def evaluate_preparation(
    snapshot: dict[str, Any],
    deck_a_name_confirmed: bool,
    deck_b_name_confirmed: bool,
) -> PreparationStatus:
    return PreparationStatus(
        midi_connected=snapshot["status"] == "connected",
        deck_a_loaded=bool(
            snapshot["deck_a"]["loaded_received"]
            and snapshot["deck_a"]["loaded"]
        ),
        deck_b_loaded=bool(
            snapshot["deck_b"]["loaded_received"]
            and snapshot["deck_b"]["loaded"]
        ),
        deck_a_name_confirmed=deck_a_name_confirmed,
        deck_b_name_confirmed=deck_b_name_confirmed,
    )
