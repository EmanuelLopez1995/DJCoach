"""Persistencia de intentos del alumno."""

from pathlib import Path

from djcoach.config import ATTEMPTS_DIRECTORY

from .take_repository import TakeRepository


class AttemptRepository(TakeRepository):
    def __init__(self, directory: Path = ATTEMPTS_DIRECTORY) -> None:
        super().__init__(directory)
