import unittest

import dj_coach_web as web


class WebDashboardTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
