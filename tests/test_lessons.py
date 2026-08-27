import copy
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
    build_guidance_moments,
    build_guidance_steps,
    compare_initial_state,
    event_matches_step,
    extract_take_features,
)
from djcoach.tracks import TrackCatalog


def complete_initial_snapshot() -> dict:
    def continuous(midi: int) -> dict:
        return {"midi": midi, "received": True}

    deck = {
        "low": continuous(63),
        "mid": continuous(63),
        "high": continuous(63),
        "gain": continuous(63),
        "fx_adjust": continuous(63),
        "volume": continuous(127),
        "track_progress": continuous(0),
        "loop_size": continuous(101),
        "loaded": True,
        "loaded_received": True,
    }
    for control in ("fx_on", "cue", "play", "loop_active", "sync"):
        deck[control] = False
        deck[f"{control}_received"] = True
    return {
        "status": "connected",
        "deck_a": copy.deepcopy(deck),
        "deck_b": copy.deepcopy(deck),
        "crossfader": continuous(63),
        "midi_clock": {
            "bpm": 136.0,
            "received": True,
            "active": True,
        },
    }


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
                    "initial_state": complete_initial_snapshot(),
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
        moments = build_guidance_moments(steps)
        self.assertEqual(len(moments), 1)
        self.assertEqual(len(moments[0]["actions"]), 2)

    def test_loop_size_is_attached_to_activation_and_guidance(self) -> None:
        take = Take(
            lesson_id="lesson_loop",
            role=TakeRole.TEACHER,
            initial_state=complete_initial_snapshot(),
            events=[
                {
                    "type": "midi_change",
                    "section": "deck_a",
                    "control": "play",
                    "value": 127,
                    "elapsed_seconds": 1.0,
                },
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "loop_size",
                    "value": 114,
                    "elapsed_seconds": 4.0,
                },
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "loop_active",
                    "value": 127,
                    "elapsed_seconds": 5.0,
                },
            ],
        )

        features = extract_take_features(take)
        loop_on = next(
            event
            for event in features["transport_events"]
            if event["control"] == "loop_active"
        )
        self.assertEqual(loop_on["loop_size_midi"], 114)
        self.assertEqual(loop_on["loop_size_label"], "16 beats (4 compases)")

        steps = build_guidance_steps(features)
        self.assertEqual(steps[0]["kind"], "selector")
        self.assertEqual(
            steps[0]["instruction"],
            "Seleccioná un LOOP de 16 beats (4 compases) en Deck B",
        )
        self.assertEqual(
            steps[1]["instruction"],
            "Activá LOOP de 16 beats (4 compases) en Deck B",
        )
        self.assertTrue(
            event_matches_step(
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "loop_size",
                    "value": 114,
                },
                steps[0],
            )
        )

    def test_loop_size_sent_immediately_after_loop_on_replaces_previous_size(self) -> None:
        take = Take(
            lesson_id="lesson_stored_loop",
            role=TakeRole.TEACHER,
            initial_state=complete_initial_snapshot(),
            events=[
                {
                    "type": "midi_change",
                    "section": "deck_a",
                    "control": "play",
                    "value": 127,
                    "elapsed_seconds": 1.0,
                },
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "loop_active",
                    "value": 127,
                    "elapsed_seconds": 5.0,
                },
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "loop_size",
                    "value": 50,
                    "elapsed_seconds": 5.02,
                },
            ],
        )

        features = extract_take_features(take)
        loop_on = next(
            event
            for event in features["transport_events"]
            if event["control"] == "loop_active"
        )
        self.assertEqual(loop_on["loop_size_label"], "1/2 beat")
        self.assertEqual(features["selector_events"], [])
        self.assertEqual(
            build_guidance_steps(features)[0]["instruction"],
            "Activá LOOP de 1/2 beat en Deck B",
        )

    def test_initial_state_comparison_uses_tolerance_and_directions(self) -> None:
        reference = complete_initial_snapshot()
        current = complete_initial_snapshot()
        current["deck_a"]["low"]["midi"] = 60
        current["deck_b"]["high"]["midi"] = 20
        current["deck_a"]["fx_on"] = True

        comparison = compare_initial_state(reference, current)
        by_control = {
            (item.section, item.control): item for item in comparison.items
        }

        self.assertTrue(by_control[("deck_a", "low")].matched)
        self.assertFalse(by_control[("deck_b", "high")].matched)
        self.assertEqual(
            by_control[("deck_b", "high")].instruction,
            "Subí HIGH Deck B",
        )
        self.assertEqual(
            by_control[("deck_a", "fx_on")].instruction,
            "Desactivá FX ON Deck A",
        )
        self.assertFalse(comparison.ready)

    def test_old_reference_without_loop_size_remains_compatible(self) -> None:
        reference = complete_initial_snapshot()
        current = complete_initial_snapshot()
        del reference["deck_a"]["loop_size"]
        del reference["deck_b"]["loop_size"]

        comparison = compare_initial_state(reference, current)

        self.assertTrue(comparison.ready)
        self.assertNotIn(
            "loop_size", {item.control for item in comparison.items}
        )

    def test_guided_practice_accepts_simultaneous_actions_in_any_order(self) -> None:
        class FakeRuntime:
            def __init__(self):
                self.events = []
                self.elapsed = 0.0

            def begin_take_capture(self):
                return {
                    "event_cursor": 0,
                    "elapsed_seconds": 0.0,
                    "initial_state": complete_initial_snapshot(),
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
            reference.initial_state = complete_initial_snapshot()
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
            self.assertEqual(
                status["current"]["actions"][0]["instruction"],
                "Cerrá LOW de Deck B",
            )

            # Las dos acciones pertenecen al mismo momento y pueden hacerse
            # en cualquier orden sin bloquearse entre sí.
            runtime.events.append(
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "play",
                    "value": 127,
                    "elapsed_seconds": 7.5,
                }
            )
            runtime.elapsed = 7.5
            status = recorder.status(lesson.id)
            self.assertEqual(status["completed_count"], 1)
            pending_actions = [
                action
                for action in status["current"]["actions"]
                if action["outcome"] is None
            ]
            self.assertEqual(
                pending_actions[0]["instruction"], "Cerrá LOW de Deck B"
            )

            runtime.events.append(
                {
                    "type": "midi_change",
                    "section": "deck_b",
                    "control": "low",
                    "value": 5,
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
