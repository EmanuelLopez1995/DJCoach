import json
import tempfile
import unittest
from pathlib import Path

from dj_coach_runtime import DJCoachRuntime
from djcoach.domain import Lesson, Take, TakeRole
from djcoach.lessons import (
    AttemptRepository,
    GuidedPracticeRecorder,
    LessonRepository,
    ReferenceTakeRecorder,
    TakeRepository,
    evaluate_preparation,
    build_guidance_steps,
    event_matches_step,
    extract_take_features,
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

    def test_feature_extractor_builds_one_ordered_technique_timeline(self) -> None:
        take = Take(
            lesson_id="lesson_test",
            role=TakeRole.TEACHER,
            events=[
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "play",
                    "value": 127,
                    "elapsed_seconds": 2.0,
                },
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "low",
                    "value": 0,
                    "elapsed_seconds": 5.0,
                },
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "low",
                    "value": 63,
                    "elapsed_seconds": 5.8,
                },
                {
                    "type": "midi_change",
                    "section": "deck_a",
                    "control": "beat_phase",
                    "value": 60,
                    "elapsed_seconds": 6.0,
                },
                {"type": "transition_started", "elapsed_seconds": 7.0},
                {
                    "type": "warning",
                    "rule": "bass_gap",
                    "message": "Ambos LOW cerrados",
                    "elapsed_seconds": 8.0,
                },
                {
                    "type": "transition_ended",
                    "elapsed_seconds": 17.0,
                    "duration_seconds": 10.0,
                },
            ],
        )

        features = extract_take_features(take)

        self.assertEqual(features["meaningful_event_count"], 3)
        self.assertEqual(features["transition"]["duration_seconds"], 10.0)
        self.assertEqual(features["gestures"][0]["control"], "low")
        self.assertEqual(features["gestures"][0]["direction"], "increase")
        self.assertTrue(features["transport_events"][0]["active"])
        self.assertNotIn("observations", features)
        self.assertEqual(
            [event["type"] for event in features["timeline"]],
            [
                "transport_change",
                "control_gesture",
                "transition_started",
                "transition_ended",
            ],
        )

    def test_guidance_reveals_action_steps_relative_to_deck_a_play(self) -> None:
        features = {
            "timeline": [
                {
                    "type": "transport_change",
                    "section": "deck_a",
                    "control": "play",
                    "active": True,
                    "elapsed_seconds": 5.0,
                },
                {
                    "type": "control_gesture",
                    "section": "deck_b",
                    "control": "low",
                    "end_value": 0,
                    "delta": -63,
                    "minimum_value": 0,
                    "maximum_value": 63,
                    "direction": "decrease",
                    "elapsed_seconds": 10.0,
                },
                {
                    "type": "transport_change",
                    "section": "deck_b",
                    "control": "play",
                    "active": True,
                    "elapsed_seconds": 12.0,
                },
            ]
        }
        steps = build_guidance_steps(features)

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["reference_seconds"], 5.0)
        self.assertEqual(steps[0]["instruction"], "Cerrá LOW de Deck B")
        self.assertTrue(
            event_matches_step(
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "low",
                    "value": 10,
                },
                steps[0],
            )
        )

    def test_guided_practice_advances_one_instruction_at_a_time(self) -> None:
        class FakeRuntime:
            def __init__(self):
                self.events = []
                self.elapsed = 0.0

            def begin_take_capture(self):
                return {
                    "event_cursor": 0,
                    "elapsed_seconds": 0.0,
                    "initial_state": {
                        "status": "connected",
                        "deck_a": {"loaded_received": True, "loaded": True},
                        "deck_b": {"loaded_received": True, "loaded": True},
                    },
                }

            def peek_take_capture(self, _checkpoint):
                return {
                    "events": list(self.events),
                    "elapsed_seconds": self.elapsed,
                    "final_state": {},
                }

            def finish_take_capture(self, _checkpoint):
                return {"events": list(self.events), "final_state": {}}

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            tracks = root / "tracks"
            tracks.mkdir()
            path_a = tracks / "A.wav"
            path_b = tracks / "B.wav"
            path_a.write_bytes(b"a")
            path_b.write_bytes(b"b")
            catalog = TrackCatalog(tracks)
            lesson = Lesson(
                name="Guided",
                deck_a_track=catalog.reference_for(path_a),
                deck_b_track=catalog.reference_for(path_b),
                status="ready_for_practice",
            )
            lessons = LessonRepository(root / "lessons")
            references = TakeRepository(root / "takes")
            attempts = AttemptRepository(root / "attempts")
            reference = Take(lesson_id=lesson.id, role=TakeRole.TEACHER)
            reference.features = {
                "timeline": [
                    {
                        "type": "transport_change",
                        "section": "deck_a",
                        "control": "play",
                        "active": True,
                        "elapsed_seconds": 5.0,
                    },
                    {
                        "type": "control_gesture",
                        "section": "deck_b",
                        "control": "low",
                        "end_value": 0,
                        "delta": -63,
                        "minimum_value": 0,
                        "maximum_value": 63,
                        "direction": "decrease",
                        "elapsed_seconds": 10.0,
                    },
                    {
                        "type": "transport_change",
                        "section": "deck_b",
                        "control": "play",
                        "active": True,
                        "elapsed_seconds": 12.0,
                    },
                ]
            }
            references.save(reference)
            lesson.reference_take_id = reference.id
            lessons.save(lesson)
            runtime = FakeRuntime()
            recorder = GuidedPracticeRecorder(
                runtime, lessons, references, attempts
            )

            recorder.start(lesson.id)
            self.assertEqual(recorder.status(lesson.id)["state"], "waiting_for_play")
            runtime.events.append(
                {
                    "type": "midi_change",
                    "section": "deck_a",
                    "control": "play",
                    "value": 127,
                    "elapsed_seconds": 1.0,
                }
            )
            runtime.elapsed = 1.0
            status = recorder.status(lesson.id)
            self.assertEqual(status["current"]["instruction"], "Cerrá LOW de Deck B")

            runtime.events.append(
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "low",
                    "value": 5,
                    "elapsed_seconds": 6.0,
                }
            )
            runtime.elapsed = 6.0
            status = recorder.status(lesson.id)
            self.assertEqual(status["completed_count"], 1)
            self.assertEqual(status["current"]["instruction"], "Activá PLAY de Deck B")

            runtime.events.append(
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "play",
                    "value": 127,
                    "elapsed_seconds": 8.0,
                }
            )
            runtime.elapsed = 8.0
            self.assertEqual(
                recorder.status(lesson.id)["state"], "guidance_complete"
            )
            attempt = recorder.stop(lesson.id)
            self.assertEqual(attempt.features["score_percentage"], 100)
            self.assertEqual(attempt.role, TakeRole.STUDENT)

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
