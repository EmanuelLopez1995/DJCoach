"""Persistencia JSON de las tomas grabadas por el profesor."""

from __future__ import annotations

import json
from pathlib import Path

from djcoach.config import TAKES_DIRECTORY, ensure_data_directories
from djcoach.domain import Take


class TakeRepository:
    def __init__(self, directory: Path = TAKES_DIRECTORY) -> None:
        self.directory = directory

    def save(self, take: Take) -> Path:
        ensure_data_directories()
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{take.id}.json"
        temporary = target.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(take.to_dict(), output, ensure_ascii=False, indent=2)
        temporary.replace(target)
        return target

    def get(self, take_id: str) -> Take:
        path = self.directory / f"{take_id}.json"
        with path.open("r", encoding="utf-8") as source:
            return Take.from_dict(json.load(source))
