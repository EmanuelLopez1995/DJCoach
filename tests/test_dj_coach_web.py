import unittest
from types import SimpleNamespace

import dj_coach_web as web
from djcoach.web.product_pages import (
    render_coach_context,
    render_coach_feedback,
    render_coach_next,
    render_coach_now,
    render_coach_timeline,
    render_guidance_moment,
    render_lesson_plan,
    render_mixer_calibration,
    render_visual_mixer,
)


class WebDashboardTests(unittest.TestCase):
    def test_lesson_plan_lists_every_action_with_time_and_loop_size(self) -> None:
        plan = render_lesson_plan(
            [
                {
                    "id": "step_001",
                    "section": "deck_b",
                    "reference_seconds": 11.2,
                    "instruction": "Activá LOOP de 4 beats (1 compás) en Deck B",
                },
                {
                    "id": "step_002",
                    "section": "mixer",
                    "reference_seconds": 12.0,
                    "instruction": "Llevá el CROSSFADER hacia Deck B",
                },
            ]
        )

        self.assertIn("0 / 2", plan)
        self.assertIn("00:11", plan)
        self.assertIn("LOOP de 4 beats (1 compás)", plan)
        self.assertIn("SIMULTÁNEAS · HACÉ AMBAS", plan)
        self.assertIn("lesson-plan-actions simultaneous", plan)

        completed = render_lesson_plan(
            [
                {
                    "id": "step_001",
                    "section": "deck_b",
                    "reference_seconds": 11.2,
                    "instruction": "Activá LOOP en Deck B",
                }
            ],
            {"step_001"},
        )
        self.assertIn("1 / 1", completed)
        self.assertIn("lesson-plan-row deck-b completed", completed)

    def test_lesson_plan_only_enables_the_current_moment(self) -> None:
        steps = [
            {
                "id": "step_001",
                "section": "deck_a",
                "reference_seconds": 10.0,
                "instruction": "Action A",
            },
            {
                "id": "step_002",
                "section": "deck_b",
                "reference_seconds": 10.2,
                "instruction": "Action B",
            },
            {
                "id": "step_003",
                "section": "mixer",
                "reference_seconds": 20.0,
                "instruction": "Future action",
            },
        ]

        initial = render_lesson_plan(steps)
        self.assertIn("lesson-plan-row deck-a current", initial)
        self.assertIn("lesson-plan-row deck-b current", initial)
        self.assertIn("lesson-plan-row mixer locked", initial)

        partially_done = render_lesson_plan(steps, {"step_001"})
        self.assertIn("lesson-plan-row deck-b current", partially_done)
        self.assertIn("lesson-plan-row mixer locked", partially_done)

        advanced = render_lesson_plan(steps, {"step_001", "step_002"})
        self.assertIn("lesson-plan-row mixer current", advanced)

    def test_visual_mixer_uses_live_midi_and_teacher_ghost(self) -> None:
        def continuous(midi: int) -> dict:
            return {"midi": midi, "received": True}

        deck = {
            control: continuous(63)
            for control in ("gain", "high", "mid", "low", "fx_adjust", "volume")
        }
        for control in ("play", "cue", "sync", "loop_active", "fx_on"):
            deck[control] = False
            deck[f"{control}_received"] = True
        mixer_state = {
            "deck_a": dict(deck),
            "deck_b": dict(deck),
            "crossfader": continuous(63),
        }
        mixer_state["deck_b"]["low"] = continuous(76)
        moment = {
            "actions": [
                {
                    "section": "deck_b",
                    "control": "low",
                    "target_value": 13,
                    "instruction": "Cerrá LOW de Deck B",
                },
                {
                    "section": "deck_b",
                    "control": "cue",
                    "target_active": True,
                    "instruction": "Activá MONITOR CUE de Deck B",
                },
            ]
        }

        page = render_visual_mixer(mixer_state, moment)

        self.assertIn("visual-mixer", page)
        self.assertIn("coach-knob-ghost", page)
        self.assertIn("60% ↓ 10%", page)
        self.assertIn("coach-mixer-button involved", page)
        self.assertIn("posición real", page)
        self.assertIn("ghost profesor", page)

    def test_student_coach_prioritizes_now_next_timeline_and_feedback(self) -> None:
        current = {
            "actions": [
                {
                    "section": "deck_b",
                    "control": "play",
                    "instruction": "Activá PLAY de Deck B",
                    "outcome": None,
                },
                {
                    "section": "deck_b",
                    "control": "cue",
                    "instruction": "Activá MONITOR CUE de Deck B",
                    "outcome": None,
                },
            ]
        }
        following = {
            "actions": [
                {
                    "section": "deck_a",
                    "control": "low",
                    "instruction": "Cerrá LOW de Deck A",
                    "outcome": None,
                },
                {
                    "section": "deck_b",
                    "control": "low",
                    "instruction": "Subí LOW de Deck B",
                    "outcome": None,
                },
            ]
        }
        status = {
            "state": "guiding",
            "current": current,
            "current_moment_number": 3,
            "total_moments": 8,
            "musical_context": {"bar": 9, "beat": 1, "bpm": 136.0},
            "timeline": [
                {"actions": current["actions"], "visual_state": "completed"},
                {"actions": following["actions"], "visual_state": "current"},
            ],
            "feedback": [
                {"state": "success", "message": "Correcto: Activá SYNC de Deck A"}
            ],
        }

        context = render_coach_context("Bass Swap Básico", status)
        timeline = render_coach_timeline(status)
        now = render_coach_now(current, "guiding", 0, 136.0)
        next_panel = render_coach_next(following, 3.6, 136.0)
        feedback = render_coach_feedback(status)

        self.assertIn("PASO</span><strong>3 de 8", context)
        self.assertIn("Compás 9 · Beat 1", context)
        self.assertIn("timeline-step current", timeline)
        self.assertIn("PREPARÁ DECK B", now)
        self.assertIn("Activá PLAY de Deck B", now)
        self.assertIn("En 2 compases · ≈ 4 s", next_panel)
        self.assertIn("BASS SWAP", next_panel)
        self.assertIn("Correcto: Activá SYNC", feedback)
        self.assertNotIn("Sin acción", now + next_panel + feedback)

    def test_current_action_is_explained_with_live_value_target_and_direction(self) -> None:
        mixer_state = {
            "deck_b": {
                "low": {"midi": 76, "received": True},
            }
        }
        current = {
            "actions": [
                {
                    "section": "deck_b",
                    "control": "low",
                    "target_value": 13,
                    "instruction": "Cerrá LOW de Deck B",
                    "outcome": None,
                }
            ]
        }

        now = render_coach_now(current, "guiding", 0, 136.0, mixer_state)

        self.assertIn("coach-focus-action", now)
        self.assertIn("coach-brief", now)
        self.assertIn("coach-stage", now)
        self.assertIn("Cerrá LOW de Deck B", now)
        self.assertIn("Actual 60% → objetivo 10% · BAJÁ ↓", now)
        self.assertIn('control-move-arrow down', now)

    def test_timeline_only_displays_the_relevant_six_phases(self) -> None:
        moments = [
            ("deck_a", "play"),
            ("deck_b", "play"),
            ("deck_a", "loop_active"),
            ("deck_b", "loop_active"),
            ("deck_a", "low"),
            ("deck_b", "low"),
            ("deck_a", "fx_adjust"),
            ("mixer", "crossfader"),
            ("deck_a", "sync"),
        ]
        status = {
            "timeline": [
                {
                    "actions": [
                        {
                            "section": section,
                            "control": control,
                            "instruction": f"Momento {index}",
                        }
                    ],
                    "visual_state": "current" if index == 6 else "pending",
                }
                for index, (section, control) in enumerate(moments)
            ]
        }

        timeline = render_coach_timeline(status)

        self.assertEqual(timeline.count('class="timeline-step '), 6)
        self.assertIn("Efecto", timeline)

    def test_mixer_calibration_looks_like_hardware_controls(self) -> None:
        items = []
        for section in ("deck_a", "deck_b"):
            for control in (
                "low",
                "mid",
                "high",
                "gain",
                "fx_adjust",
                "volume",
                "track_progress",
            ):
                value = 127 if control == "volume" else 63
                items.append(
                    SimpleNamespace(
                        section=section,
                        control=control,
                        target=value,
                        current=value,
                        target_display=f"MIDI {value}",
                        current_display=f"MIDI {value}",
                        matched=True,
                        instruction="Posición correcta",
                    )
                )
            for control in ("fx_on", "cue", "play", "loop_active", "sync"):
                items.append(
                    SimpleNamespace(
                        section=section,
                        control=control,
                        target=False,
                        current=False,
                        target_display="OFF",
                        current_display="OFF",
                        matched=True,
                        instruction="Posición correcta",
                    )
                )
        items.extend(
            [
                SimpleNamespace(
                    section="mixer", control="crossfader", target=63,
                    current=63, target_display="MIDI 63",
                    current_display="MIDI 63", matched=True,
                    instruction="Posición correcta",
                ),
                SimpleNamespace(
                    section="mixer", control="master_clock", target=True,
                    current=True, target_display="ON", current_display="ON",
                    matched=True, instruction="Posición correcta",
                ),
                SimpleNamespace(
                    section="mixer", control="master_bpm", target=136.0,
                    current=136.0, target_display="136.0 BPM",
                    current_display="136.0 BPM", matched=True,
                    instruction="Posición correcta",
                ),
            ]
        )
        page = render_mixer_calibration(SimpleNamespace(items=items))

        self.assertIn('class="knob-face"', page)
        self.assertIn('class="vertical-fader"', page)
        self.assertIn("CROSSFADER", page)
        self.assertIn("Posición actual", page)
        self.assertLess(page.index("DECK A"), page.index("MIXER / CLOCK"))
        self.assertLess(page.index("MIXER / CLOCK"), page.index("DECK B"))

    def test_guidance_moment_separates_deck_and_mixer_lanes(self) -> None:
        page = render_guidance_moment(
            {
                "actions": [
                    {
                        "section": "deck_a",
                        "instruction": "Bajá HIGH de Deck A",
                        "outcome": None,
                    },
                    {
                        "section": "deck_b",
                        "instruction": "Subí HIGH de Deck B",
                        "outcome": {"status": "completed"},
                    },
                ]
            },
            "AHORA",
            "current",
        )
        self.assertIn("DECK A", page)
        self.assertIn("DECK B", page)
        self.assertIn("MIXER / GLOBAL", page)
        self.assertIn("Bajá HIGH de Deck A", page)
        self.assertIn('class="lane-action done"', page)

    def test_initial_dashboard_contains_main_sections(self) -> None:
        page = web.render_dashboard(web.runtime.snapshot())
        self.assertIn("DJ COACH", page)
        self.assertIn("DECK A", page)
        self.assertIn("DECK B", page)
        self.assertIn("CROSSFADER", page)
        self.assertIn("LOCAL COACH ENGINE", page)
        self.assertIn("PROGRESO DE CANCIÓN", page)
        self.assertIn("TRACK END", page)
        self.assertIn("MASTER CLOCK", page)
        self.assertIn("BPM ACTUAL", page)
        self.assertIn("Esperando MIDI", page)

    def test_dashboard_shows_recent_warnings(self) -> None:
        snapshot = web.runtime.snapshot()
        snapshot["coach"]["warning_history"] = [
            {
                "timestamp": "2026-08-26T22:00:00",
                "rule": "bass_overlap",
                "message": "Ambos graves están abiertos",
            }
        ]
        page = web.render_dashboard(snapshot)
        self.assertIn("AVISOS RECIENTES", page)
        self.assertIn("Ambos graves están abiertos", page)

    def test_dashboard_marks_positive_feedback_as_success(self) -> None:
        snapshot = web.runtime.snapshot()
        snapshot["coach"]["warning_history"] = [
            {
                "timestamp": "2026-08-26T22:00:00",
                "rule": "phase_recovered",
                "message": "La fase volvió a una zona alineada.",
                "severity": "success",
            }
        ]
        page = web.render_dashboard(snapshot)
        self.assertIn('class="success"', page)
        self.assertIn("La fase volvió a una zona alineada.", page)

    def test_dashboard_shows_rhythm_counters(self) -> None:
        snapshot = web.runtime.snapshot()
        tempo = snapshot["deck_tempos"]["a"]
        tempo.update(
            {
                "downbeat_set": True,
                "beat_in_bar": 3,
                "bar_count": 10,
                "bar_in_block": {"4": 2, "8": 2, "16": 10, "32": 10},
                "block_count": {"4": 3, "8": 2, "16": 1, "32": 1},
            }
        )
        page = web.render_dashboard(snapshot)
        self.assertIn("RITMO 4/4", page)
        self.assertIn("COMPÁS 10", page)
        self.assertIn("BLOQUE 32", page)


if __name__ == "__main__":
    unittest.main()
