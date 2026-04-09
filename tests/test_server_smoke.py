import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "purple_car_bench_agent"))

from server import prepare_agent_card  # noqa: E402


class ServerSmokeTests(unittest.TestCase):
    def test_prepare_agent_card_fields(self) -> None:
        card = prepare_agent_card("http://127.0.0.1:8080/")
        self.assertEqual(card.name, "car_bench_agent")
        self.assertEqual(card.url, "http://127.0.0.1:8080/")
        self.assertIn("text/plain", card.default_input_modes)
        self.assertIn("text/plain", card.default_output_modes)
        self.assertGreaterEqual(len(card.skills), 1)
        self.assertEqual(card.skills[0].id, "car_assistant")


if __name__ == "__main__":
    unittest.main()
