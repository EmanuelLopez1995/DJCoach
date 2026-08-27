import json
import tempfile
import unittest
from pathlib import Path

from dj_coach_runtime import DJCoachRuntime
from djcoach.domain import Lesson, Take, TakeRole
from djcoach.lessons import (
    LessonRepository,
    ReferenceTakeRecorder,
    TakeRepository,
    evaluate_preparation,
)
from djcoach.tracks import TrackCatalog


class LessonDomainTests(unittest.TestCase):
    def test_catalog_hashes_tracks_and_repository_round_trips_lesson(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            tracks_directory = root / "tracks"
            tracks_directory.mkdir()
            track_a_path = tracks_directory / "Track A.wav"
            track_b_path = tracks_directory / "Track B.aiff"
            track_a_path.write_bytes(b"track-a")
            track_b_path.write_bytes(b"track-b")

            catalog = TrackCatalog(tracks_directory)
            paths = catalog.list_paths()
            self.assertEqual(paths, [track_a_path, track_b_path])
            track_a = catalog.reference_for(track_a_path)
            track_b = catalog.reference_for(track_b_path)
            lesson = Lesson(
                name="Bass swap básico",
                deck_a_track=track_a,
                deck_b_track=track_b,
            )
            repository = LessonRepository(root / "lessons")
            saved_path = repository.save(lesson)
            restored = repository.get(lesson.id)

            self.assertTrue(saved_path.exists())
            self.assertEqual(restored.to_dict(), lesson.to_dict())
            self.assertEqual(repository.list()[0].name, "Bass swap básico")
            payload = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)

    def test_take_serializes_role_as_string(self) -> None:
        take = Take(lesson_id="lesson_test", role=TakeRole.TEACHER)
        self.assertEqual(take.to_dict()["role"], "teacher")

    def test_take_repository_round_trips_extended_recording(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            repository = TakeRepository(Path(temporary_directory))
            take = Take(
                lesson_id="lesson_test",
                role=TakeRole.TEACHER,
                duration_seconds=12.5,
                initial_state={"deck_a": {"play": False}},
                final_state={"deck_a": {"play": True}},
                events=[{"type": "midi_change", "elapsed_seconds": 1.2}],
            )
            repository.save(take)
            restored = repository.get(take.id)

            self.assertEqual(restored.to_dict(), take.to_dict())

    def test_reference_recorder_saves_take_and_updates_lesson(self) -> None:
        class FakeRuntime:
            def begin_take_capture(self):
                return {
                    "event_cursor": 4,
                    "elapsed_seconds": 20.0,
                    "initial_state": {
                        "status": "connected",
                        "deck_a": {"loaded_received": True, "loaded": True},
                        "deck_b": {"loaded_received": True, "loaded": True},
                    },
                }

            def finish_take_capture(self, _checkpoint):
                return {
                    "events": [
                        {
                            "type": "midi_change",
                            "control": "crossfader",
                            "elapsed_seconds": 1.25,
                        }
                    ],
                    "final_state": {"status": "connected"},
                }

            def take_event_count(self, _checkpoint):
                return 1

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            tracks_directory = root / "tracks"
            tracks_directory.mkdir()
            path_a = tracks_directory / "A.wav"
            path_b = tracks_directory / "B.wav"
            path_a.write_bytes(b"a")
            path_b.write_bytes(b"b")
            catalog = TrackCatalog(tracks_directory)
            lesson = Lesson(
                name="Reference",
                deck_a_track=catalog.reference_for(path_a),
                deck_b_track=catalog.reference_for(path_b),
            )
            lessons = LessonRepository(root / "lessons")
            takes = TakeRepository(root / "takes")
            lessons.save(lesson)
            recorder = ReferenceTakeRecorder(FakeRuntime(), lessons, takes)

            recorder.start(lesson.id)
            saved_take = recorder.stop(lesson.id)
            updated_lesson = lessons.get(lesson.id)

            self.assertEqual(updated_lesson.reference_take_id, saved_take.id)
            self.assertEqual(updated_lesson.status, "reference_recorded")
            self.assertEqual(takes.get(saved_take.id).events, saved_take.events)
            self.assertEqual(saved_take.features["midi_change_count"], 1)

    def test_runtime_capture_uses_only_new_events_and_rebases_time(self) -> None:
        runtime = DJCoachRuntime()
        runtime.recorder.events.append(
            {"type": "midi_change", "elapsed_seconds": 1.0}
        )
        checkpoint = runtime.begin_take_capture()
        runtime.recorder.events.append(
            {
                "type": "midi_change",
                "elapsed_seconds": checkpoint["elapsed_seconds"] + 1.25,
            }
        )

        self.assertEqual(runtime.take_event_count(checkpoint), 1)
        result = runtime.finish_take_capture(checkpoint)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["elapsed_seconds"], 1.25)

    def test_preparation_requires_midi_loaded_decks_and_name_confirmation(self) -> None:
        snapshot = {
            "status": "connected",
            "deck_a": {"loaded_received": True, "loaded": True},
            "deck_b": {"loaded_received": True, "loaded": True},
        }
        incomplete = evaluate_preparation(snapshot, True, False)
        complete = evaluate_preparation(snapshot, True, True)

        self.assertFalse(incomplete.ready)
        self.assertTrue(complete.ready)

    def test_preparation_rejects_stale_or_empty_loaded_state(self) -> None:
        snapshot = {
            "status": "connected",
            "deck_a": {"loaded_received": False, "loaded": False},
            "deck_b": {"loaded_received": True, "loaded": True},
        }
        self.assertFalse(evaluate_preparation(snapshot, True, True).ready)


if __name__ == "__main__":
    unittest.main()
