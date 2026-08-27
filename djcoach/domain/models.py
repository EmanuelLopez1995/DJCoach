"""Modelos persistibles para el flujo Profesor → Alumno."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class TakeRole(StrEnum):
    TEACHER = "teacher"
    STUDENT = "student"


@dataclass(frozen=True)
class TrackReference:
    id: str
    title: str
    filename: str
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass
class Take:
    lesson_id: str
    role: TakeRole
    id: str = field(default_factory=lambda: new_id("take"))
    started_at: str = field(default_factory=timestamp_now)
    ended_at: str | None = None
    duration_seconds: float | None = None
    initial_state: dict[str, Any] = field(default_factory=dict)
    final_state: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["role"] = self.role.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Take:
        data = dict(payload)
        data["role"] = TakeRole(data["role"])
        return cls(**data)


@dataclass
class Lesson:
    name: str
    deck_a_track: TrackReference
    deck_b_track: TrackReference
    id: str = field(default_factory=lambda: new_id("lesson"))
    description: str = ""
    status: str = "draft"
    created_at: str = field(default_factory=timestamp_now)
    updated_at: str = field(default_factory=timestamp_now)
    reference_take_id: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Lesson:
        data = dict(payload)
        data["deck_a_track"] = TrackReference(**data["deck_a_track"])
        data["deck_b_track"] = TrackReference(**data["deck_b_track"])
        return cls(**data)
