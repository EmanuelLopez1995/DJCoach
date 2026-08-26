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
        self.assertIn("Esperando MIDI", page)


if __name__ == "__main__":
    unittest.main()

