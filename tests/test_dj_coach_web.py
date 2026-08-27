import unittest

import dj_coach_web as web
from djcoach.web.product_pages import render_guidance_moment


class WebDashboardTests(unittest.TestCase):
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
