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
        self.assertEqual(incoming.get_nowait().message, messages[0])
        self.assertEqual(incoming.get_nowait().message, messages[1])

    def test_midi_clock_calculates_current_bpm_and_detects_stop(self) -> None:
        midi_clock = dj.create_midi_clock_state()
        interval = 60 / (120 * dj.MIDI_CLOCK_PULSES_PER_BEAT)
        for index in range(240):
            dj.update_midi_clock(
                midi_clock,
                mido.Message("clock"),
                10.0 + index * interval,
            )

        self.assertTrue(midi_clock["received"])
        self.assertTrue(midi_clock["active"])
        self.assertAlmostEqual(midi_clock["bpm"], 120.0, places=1)
        self.assertTrue(dj.refresh_midi_clock(midi_clock, now=20.0))
        self.assertFalse(midi_clock["active"])

    def test_midi_clock_rejects_delivery_jitter(self) -> None:
        midi_clock = dj.create_midi_clock_state()
        interval = 60 / (131 * dj.MIDI_CLOCK_PULSES_PER_BEAT)
        base_time = 30.0
        for index in range(480):
            ideal_time = base_time + index * interval
            batched_time = round(ideal_time / 0.01) * 0.01
            dj.update_midi_clock(
                midi_clock,
                mido.Message("clock"),
                batched_time,
            )

        self.assertAlmostEqual(midi_clock["bpm"], 131.0, delta=0.1)

    def test_each_deck_bpm_is_calculated_from_beat_phase_wraps(self) -> None:
        tempos = dj.create_deck_tempos_state()
        for index in range(120):
            elapsed = index * 0.05
            phase_a = int(((elapsed * 136 / 60) % 1) * 127)
            dj.update_deck_tempo_from_beat_phase(
                tempos, cc(30, phase_a), 20.0 + elapsed
            )
            phase_b = int(((elapsed * 120 / 60) % 1) * 127)
            dj.update_deck_tempo_from_beat_phase(
                tempos, cc(31, phase_b), 20.0 + elapsed
            )

        self.assertAlmostEqual(tempos["a"]["bpm"], 136.0, delta=0.2)
        self.assertAlmostEqual(tempos["b"]["bpm"], 120.0, delta=0.2)
        self.assertTrue(tempos["a"]["active"])
        self.assertTrue(dj.refresh_deck_tempos(tempos, now=29.0))
        self.assertFalse(tempos["a"]["active"])

    def test_deck_bpm_rejects_batched_beat_phase_jitter(self) -> None:
        tempos = dj.create_deck_tempos_state()
        for index in range(180):
            elapsed = index * 0.04
            phase = int(((elapsed * 131 / 60) % 1) * 127)
            delivered_at = round((40.0 + elapsed) / 0.01) * 0.01
            dj.update_deck_tempo_from_beat_phase(
                tempos, cc(30, phase), delivered_at
            )

        self.assertAlmostEqual(tempos["a"]["bpm"], 131.0, delta=0.2)

    def test_synced_deck_uses_master_bpm_and_unsynced_deck_uses_measurement(self) -> None:
        deck_a = dj.create_deck_a_state()
        deck_b = dj.create_deck_b_state()
        dj.update_deck_a(deck_a, cc(26, 127))
        dj.update_deck_b(deck_b, cc(27, 0))
        midi_clock = dj.create_midi_clock_state()
        midi_clock.update(
            {"received": True, "active": True, "bpm": 131.0}
        )
        measured_a = dj.create_deck_tempo_state()
        measured_a.update(
            {"received": True, "active": False, "bpm": 132.5}
        )
        measured_b = dj.create_deck_tempo_state()
        measured_b.update(
            {"received": True, "active": True, "bpm": 130.2}
        )

        bpm_a, source_a, _active_a = dj.effective_deck_bpm(
            deck_a, measured_a, midi_clock
        )
        bpm_b, source_b, _active_b = dj.effective_deck_bpm(
            deck_b, measured_b, midi_clock
        )

        self.assertEqual(bpm_a, 131.0)
        self.assertEqual(source_a, "SYNC / MASTER")
        self.assertEqual(bpm_b, 130.2)
        self.assertEqual(source_b, "BEAT PHASE")

    def test_manual_downbeat_counts_beats_bars_and_phrase_blocks(self) -> None:
        tempos = dj.create_deck_tempos_state()
        dj.arm_deck_downbeat(tempos, "a")

        for beat_index in range(33):
            beat_at = 60.0 + beat_index * 0.5
            dj.update_deck_tempo_from_beat_phase(
                tempos, cc(30, 110), beat_at - 0.05
            )
            dj.update_deck_tempo_from_beat_phase(
                tempos, cc(30, 5), beat_at
            )

        rhythm = tempos["a"]
        self.assertTrue(rhythm["downbeat_set"])
        self.assertFalse(rhythm["downbeat_armed"])
        self.assertEqual(rhythm["beat_in_bar"], 1)
        self.assertEqual(rhythm["bar_count"], 9)
        self.assertEqual(rhythm["bar_in_block"], {"4": 1, "8": 1, "16": 9, "32": 9})
        self.assertEqual(rhythm["block_count"], {"4": 3, "8": 2, "16": 1, "32": 1})

    def test_loading_a_track_clears_rhythm_calibration(self) -> None:
        tempos = dj.create_deck_tempos_state()
        dj.arm_deck_downbeat(tempos, "a")
        dj.update_deck_tempo_from_beat_phase(tempos, cc(30, 110), 80.0)
        dj.update_deck_tempo_from_beat_phase(tempos, cc(30, 5), 80.1)
        self.assertTrue(tempos["a"]["downbeat_set"])

        dj.update_deck_tempo_from_beat_phase(tempos, cc(20, 127), 81.0)

        self.assertFalse(tempos["a"]["downbeat_set"])
        self.assertEqual(tempos["a"]["beat_count"], 0)

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
        self.assertTrue(dj.update_deck_a(deck_a, cc(32, 64)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(33, 100)))
        self.assertTrue(dj.update_deck_a(deck_a, cc(34, 127)))
        self.assertTrue(dj.update_deck_b(deck_b, cc(35, 0)))
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
        self.assertEqual(deck_a["track_progress"]["percentage"], 50)
        self.assertEqual(deck_b["track_progress"]["midi"], 100)
        self.assertTrue(deck_a["track_end_warning"])
        self.assertFalse(deck_b["track_end_warning"])
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
        self.assertEqual(events[0]["duration_seconds"], 2.0)
        self.assertEqual(events[1]["rule"], "transition_too_fast")

    def test_bass_gap_warning_requires_hold_time(self) -> None:
        dj.update_deck_a(self.deck_a, cc(1, 10))
        dj.update_deck_b(self.deck_b, cc(9, 10))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=20.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=21.5
        )
        self.assertEqual(events[0]["rule"], "bass_gap")

    def test_phase_warning_is_generic_and_requires_both_decks_audible(self) -> None:
        dj.update_deck_a(self.deck_a, cc(28, 10))
        dj.update_deck_b(self.deck_b, cc(29, 63))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=30.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=31.0
        )
        warning = next(event for event in events if event.get("rule") == "beats_out_of_phase")
        self.assertIn("MIDI 10", warning["message"])
        self.assertNotIn("adelant", warning["message"])
        self.assertNotIn("atras", warning["message"])

    def test_phase_recovery_is_reported_after_a_real_warning(self) -> None:
        dj.update_deck_a(self.deck_a, cc(28, 10))
        dj.update_deck_b(self.deck_b, cc(29, 63))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=32.0
        )
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=33.0
        )

        dj.update_deck_a(self.deck_a, cc(28, 63))
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=33.1
        )

        recovery = next(event for event in events if event.get("rule") == "phase_recovered")
        self.assertEqual(recovery["type"], "feedback")
        self.assertTrue(self.coach["feedback"].startswith("BIEN:"))

    def test_stopping_a_deck_does_not_claim_phase_was_fixed(self) -> None:
        dj.update_deck_a(self.deck_a, cc(28, 10))
        dj.update_deck_b(self.deck_b, cc(29, 63))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=34.0
        )
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=35.0
        )
        dj.update_deck_b(self.deck_b, cc(19, 0))
        dj.update_deck_a(self.deck_a, cc(28, 63))
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=35.1
        )
        self.assertFalse(any(event.get("rule") == "phase_recovered" for event in events))

    def test_long_transition_warning_fires_once(self) -> None:
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=40.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=85.0
        )
        self.assertEqual(events[0]["rule"], "transition_too_slow")
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=90.0
        )
        self.assertFalse(any(event.get("rule") == "transition_too_slow" for event in events))

    def test_abrupt_volume_change_is_recorded_in_warning_history(self) -> None:
        dj.update_deck_a(self.deck_a, cc(6, 0))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=100.0
        )
        dj.update_deck_a(self.deck_a, cc(6, 64))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=100.1
        )
        dj.update_deck_a(self.deck_a, cc(6, 127))
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=100.2
        )
        warning = next(event for event in events if event.get("rule") == "fader_abrupt_change")
        self.assertIn("VOLUME Deck A", warning["message"])
        self.assertEqual(self.coach["warning_history"][-1]["rule"], "fader_abrupt_change")

    def test_audibility_waits_for_required_controls(self) -> None:
        empty_a = dj.create_deck_a_state()
        empty_b = dj.create_deck_b_state()
        empty_crossfader = dj.make_continuous_value()
        self.assertIsNone(dj.estimate_audible(empty_a, empty_crossfader, "a"))
        self.assertIsNone(dj.estimate_audible(empty_b, empty_crossfader, "b"))

    def test_track_end_warning_is_emitted_once_per_activation(self) -> None:
        dj.update_deck_a(self.deck_a, cc(34, 127))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=120.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=120.1
        )
        warning = next(event for event in events if event.get("rule") == "track_end_warning")
        self.assertIn("Deck A", warning["message"])
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=121.0
        )
        self.assertFalse(any(event.get("rule") == "track_end_warning" for event in events))

    def test_silence_warning_when_active_volumes_are_closed(self) -> None:
        dj.update_deck_a(self.deck_a, cc(6, 0))
        dj.update_deck_b(self.deck_b, cc(17, 0))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=130.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=130.75
        )
        warning = next(event for event in events if event.get("rule") == "silence_low_volumes")
        self.assertIn("VOLUME cerrado", warning["message"])

    def test_silence_warning_when_crossfader_blocks_playing_deck(self) -> None:
        dj.update_deck_b(self.deck_b, cc(19, 0))
        dj.update_crossfader(self.crossfader, cc(16, 127))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=140.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=140.75
        )
        warning = next(event for event in events if event.get("rule") == "silence_crossfader")
        self.assertIn("Deck A", warning["message"])

    def test_silence_warning_when_active_deck_eq_is_fully_cut(self) -> None:
        dj.update_deck_b(self.deck_b, cc(19, 0))
        dj.update_deck_a(self.deck_a, cc(1, 0))
        dj.update_deck_a(self.deck_a, cc(2, 0))
        dj.update_deck_a(self.deck_a, cc(3, 0))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=150.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=150.75
        )
        warning = next(event for event in events if event.get("rule") == "silence_eq_cut")
        self.assertIn("Deck A", warning["message"])

    def test_silence_rules_do_not_warn_while_decks_are_paused(self) -> None:
        dj.update_deck_a(self.deck_a, cc(18, 0))
        dj.update_deck_b(self.deck_b, cc(19, 0))
        dj.update_deck_a(self.deck_a, cc(6, 0))
        dj.update_deck_b(self.deck_b, cc(17, 0))
        dj.update_deck_a(self.deck_a, cc(1, 0))
        dj.update_deck_a(self.deck_a, cc(2, 0))
        dj.update_deck_a(self.deck_a, cc(3, 0))
        dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=160.0
        )
        _changed, events = dj.evaluate_coach(
            self.deck_a, self.deck_b, self.crossfader, self.coach, now=162.0
        )
        self.assertFalse(any(str(event.get("rule", "")).startswith("silence_") for event in events))


class SessionTests(unittest.TestCase):
    def test_high_frequency_timing_events_are_sampled(self) -> None:
        recorder = dj.SessionRecorder()
        self.assertTrue(recorder.record_midi(cc(30, 1)))
        self.assertFalse(recorder.record_midi(cc(30, 2)))
        self.assertEqual(len(recorder.events), 1)

    def test_session_is_saved_as_json(self) -> None:
        recorder = dj.SessionRecorder()
        recorder.record_midi(cc(1, 64))
        recorder.record_analysis(
            {"type": "warning", "rule": "bass_gap", "message": "test"}
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            midi_clock = dj.create_midi_clock_state()
            midi_clock.update({"received": True, "active": True, "bpm": 128.0})
            with patch.object(dj, "SESSION_DIRECTORY", Path(temporary_directory)):
                path = recorder.save(
                    dj.create_deck_a_state(),
                    dj.create_deck_b_state(),
                    dj.make_continuous_value(),
                    midi_clock,
                )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["midi_changes"], 1)
        self.assertEqual(payload["summary"]["warnings_by_rule"], {"bass_gap": 1})
        self.assertEqual(payload["final_state"]["midi_clock"]["bpm"], 128.0)
        self.assertNotIn("_tick_times", payload["final_state"]["midi_clock"])
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
