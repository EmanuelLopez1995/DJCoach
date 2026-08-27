import unittest
from types import SimpleNamespace

import dj_coach_web as web
from djcoach.web.product_pages import (
    render_guidance_moment,
    render_mixer_calibration,
)


class WebDashboardTests(unittest.TestCase):
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
