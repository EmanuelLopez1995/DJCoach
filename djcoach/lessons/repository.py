"""Repositorio JSON local, versionado y con escritura atómica."""

from __future__ import annotations

import json
from pathlib import Path

from djcoach.config import LESSONS_DIRECTORY, ensure_data_directories
from djcoach.domain import Lesson


class LessonRepository:
    def __init__(self, directory: Path = LESSONS_DIRECTORY) -> None:
        self.directory = directory

    def save(self, lesson: Lesson) -> Path:
        ensure_data_directories()
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{lesson.id}.json"
        temporary = target.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(lesson.to_dict(), output, ensure_ascii=False, indent=2)
        temporary.replace(target)
        return target

    def get(self, lesson_id: str) -> Lesson:
        path = self.directory / f"{lesson_id}.json"
        with path.open("r", encoding="utf-8") as source:
            return Lesson.from_dict(json.load(source))

    def list(self) -> list[Lesson]:
        if not self.directory.exists():
            return []
        lessons = []
        for path in sorted(self.directory.glob("lesson_*.json")):
            with path.open("r", encoding="utf-8") as source:
                lessons.append(Lesson.from_dict(json.load(source)))
        return sorted(lessons, key=lambda lesson: lesson.created_at, reverse=True)
