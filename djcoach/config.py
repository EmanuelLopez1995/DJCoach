"""Rutas y configuración local compartida por DJ Coach."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"
TRACKS_DIRECTORY = DATA_DIRECTORY / "tracks"
DEMO_TRACKS_DIRECTORY = TRACKS_DIRECTORY / "demo"
LESSONS_DIRECTORY = DATA_DIRECTORY / "lessons"
TAKES_DIRECTORY = DATA_DIRECTORY / "takes"
ATTEMPTS_DIRECTORY = DATA_DIRECTORY / "attempts"
LEGACY_SESSIONS_DIRECTORY = PROJECT_ROOT / "sessions"


def ensure_data_directories() -> None:
    for directory in (
        DEMO_TRACKS_DIRECTORY,
        LESSONS_DIRECTORY,
        TAKES_DIRECTORY,
        ATTEMPTS_DIRECTORY,
    ):
        directory.mkdir(parents=True, exist_ok=True)
