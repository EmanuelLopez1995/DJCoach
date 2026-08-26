import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mido

import dj_coach as dj


def cc(control: int, value: int, channel: int = 0) -> mido.Message:
    return mido.Message(
        "control_change", channel=channel, control=control, value=value
    )


class MixerStateTests(unittest.TestCase):
    def test_blocking_reader_forwards_messages(self) -> None:
        incoming = queue.Queue()
        messages = [cc(1, 63), cc(16, 64)]
        dj.read_midi_messages(messages, incoming)
        self.assertEqual(incoming.get_nowait(), messages[0])
        self.assertEqual(incoming.get_nowait(), messages[1])

    def test_unknown_is_different_from_midi_zero(self) -> None:
        deck = dj.create_deck_a_state()
        self.assertFalse(deck["low"]["received"])
        self.assertIsNone(deck["low"]["midi"])

        self.assertTrue(dj.update_deck_a(deck, cc(1, 0)))
        self.assertTrue(deck["low"]["received"])
        self.assertEqual(deck["low"]["midi"], 0)
        self.assertEqual(deck["low"]["percentage"], 0)

    def test_exact_mappings_and_wrong_channel(self) -> None:
        deck_a = dj.create_deck_a_state()
        deck_b = dj.create_deck_b_state()
        crossfader = dj.make_continuous_value()

        self.assertTrue(dj.update_deck_a(deck_a, cc(6, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(9, 63)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(14, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(17, 100)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(18, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(19, 127)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(20, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(21, 127)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(22, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(23, 127)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(24, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(25, 127)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(26, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(27, 127)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(28, 64)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(29, 65)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(30, 10)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(31, 20)))
        self.assertTrue(dj.update_crossfader(crossfader, cc(16, 64)))
        self.assertFalse(dj.update_deck_b(deck_b, cc(9, 10, channel=1)))

        self.assertEqual(deck_a["volume"]["midi"], 127)
        self.assertEqual(deck_b["low"]["percentage"], 50)
        self.assertTrue(deck_b["fx_on"])
        self.assertEqual(deck_b["volume"]["midi"], 100)
        self.assertTrue(deck_a["play"])
        self.assertTrue(deck_b["play"])
        self.assertTrue(deck_a["loaded"])
        self.assertTrue(deck_b["loaded"])
        self.assertTrue(deck_a["transport_cue"])
        self.assertTrue(deck_b["loop_active"])
        self.assertTrue(deck_a["sync"])
        self.assertEqual(deck_a["phase"]["midi"], 64)
        self.assertEqual(deck_b["beat_phase"]["midi"], 20)
        self.assertEqual(crossfader["percentage"], 50)


class CoachEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.deck_a = dj.create_deck_a_state()
        self.deck_b = dj.create_deck_b_state()
        self.crossfader = dj.make_continuous_value()
        self.coach = dj.create_coach_state()

        dj.update_deck_a(self.deck_a, cc(1, 110))
        dj.update_deck_a(self.deck_a, cc(6, 127))
        dj.update_deck_b(self.deck_b, cc(9, 110))
        dj.update_deck_b(self.deck_b, cc(17, 127))
        dj.update_deck_a(self.deck_a, cc(18, 127))
        dj.update_deck_b(self.deck_b, cc(19, 127))
        dj.update_deck_a(self.deck_a, cc(20, 127))
        dj.update_deck_b(self.deck_b, cc(21, 127))
        dj.update_crossfader(self.crossfader, cc(16, 64))

    def test_transition_and_bass_overlap_timers(self) -> None:
        changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=10.0
        )
        self.assertTrue(changed)
        self.assertEqual(events, [{"type": "transition_started"}])
        self.assertTrue(self.coach["transition_active"])

        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=11.5
        )
        self.assertEqual(events[0]["rule"], "bass_overlap")

        dj.update_deck_b(self.deck_b, cc(17, 0))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=12.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=13.0
        )
        self.assertEqual(events[0]["type"], "transition_ended")
        self.assertEqual(events[0]["duration_seconds"], 3.0)

    def test_audibility_waits_for_required_controls(self) -> None:
        empty_a = dj.create_deck_a_state()
        empty_b = dj.create_deck_b_state()
        empty_crossfader = dj.make_continuous_value()
        self.assertIsNone(dj.estimate_audible(empty_a, empty_crossfader, "a"))
        self.assertIsNone(dj.estimate_audible(empty_b, empty_crossfader, "b"))


class SessionTests(unittest.TestCase):
    def test_high_frequency_timing_events_are_sampled(self) -> None:
        recorder = dj.SessionRecorder()
        self.assertTrue(recorder.record_midi(cc(30, 1)))
        self.assertFalse(recorder.record_midi(cc(30, 2)))
        self.assertEqual(len(recorder.events), 1)

    def test_session_is_saved_as_json(self) -> None:
        recorder = dj.SessionRecorder()
        recorder.record_midi(cc(1, 64))
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(dj, "SESSION_DIRECTORY", Path(temporary_directory)):
                path = recorder.save(
                    dj.create_deck_a_state(),
                    dj.create_deck_b_state(),
                    dj.make_continuous_value(),
                )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["midi_changes"], 1)
        self.assertEqual(payload["events"][0]["cc"], 1)

    def test_main_saves_session_after_ctrl_c(self) -> None:
        class FakePort:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter(())

        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch.object(dj, "SESSION_DIRECTORY", Path(temporary_directory)),
                patch.object(dj.mido, "get_input_names", return_value=["djCoach 1"]),
                patch.object(dj.mido, "open_input", return_value=FakePort()),
                patch.object(dj.queue.Queue, "get", side_effect=KeyboardInterrupt),
                patch.object(dj, "render_dashboard"),
                patch.object(dj, "enable_ansi_on_windows", return_value=True),
                patch("sys.argv", ["dj_coach.py"]),
            ):
                result = dj.main()
            session_files = list(Path(temporary_directory).glob("session_*.json"))

        self.assertEqual(result, 0)
        self.assertEqual(len(session_files), 1)


if __name__ == "__main__":
    unittest.main()
