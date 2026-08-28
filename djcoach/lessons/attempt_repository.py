"""Persistencia de intentos del alumno."""

from pathlib import Path

from djcoach.config import ATTEMPTS_DIRECTORY

from .take_repository import TakeRepository


class AttemptRepository(TakeRepository):
    def __init__(self, directory: Path = ATTEMPTS_DIRECTORY) -> None:
        super().__init__(directory)

    def list_for_lesson(self, lesson_id: str) -> list:
        """Intentos locales, más reciente primero, para habilitar reintentos."""
        if not self.directory.exists():
            return []
        attempts = []
        for path in self.directory.glob("take_*.json"):
            try:
                attempt = self.get(path.stem)
            except (OSError, ValueError):
                continue
            if attempt.lesson_id == lesson_id:
                attempts.append(attempt)
        return sorted(attempts, key=lambda item: item.started_at, reverse=True)
