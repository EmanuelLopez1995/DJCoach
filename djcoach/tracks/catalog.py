"""Indexación mínima y reproducible de archivos musicales locales."""

from __future__ import annotations

import hashlib
from pathlib import Path

from djcoach.config import PROJECT_ROOT
from djcoach.domain import TrackReference


AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a"}


class TrackCatalog:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def list_paths(self) -> list[Path]:
        if not self.directory.exists():
            return []
        return sorted(
            (
                path
                for path in self.directory.rglob("*")
                if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
            ),
            key=lambda path: path.name.casefold(),
        )

    def reference_for(self, path: Path) -> TrackReference:
        resolved = path.resolve()
        if resolved not in self.list_paths():
            raise ValueError("La canción no pertenece al catálogo configurado.")

        digest = hashlib.sha256()
        with resolved.open("rb") as audio_file:
            for chunk in iter(lambda: audio_file.read(1024 * 1024), b""):
                digest.update(chunk)

        relative_path = resolved.relative_to(PROJECT_ROOT).as_posix()
        return TrackReference(
            id=f"sha256:{digest.hexdigest()}",
            title=resolved.stem,
            filename=resolved.name,
            relative_path=relative_path,
            size_bytes=resolved.stat().st_size,
            sha256=digest.hexdigest(),
        )
