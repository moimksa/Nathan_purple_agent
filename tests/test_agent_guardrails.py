import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "purple_car_bench_agent"))

from agent_guardrails import (  # noqa: E402
    index_tools_by_name,
    map_tool_results_to_history,
    should_block_unverified_completion,
    validate_tool_calls,
)


def _tool_def(name: str, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {
                "type": "object",
                "properties": {field: {"type": "string"} for field in required},
                "required": required,
            },
        },
    }


class GuardrailTests(unittest.TestCase):
    def test_validate_tool_calls_detects_missing_required(self) -> None:
        tools_by_name = index_tools_by_name([_tool_def("navigate_to", ["destination"])])
        report = validate_tool_calls(
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "navigate_to", "arguments": "{}"},
                }
            ],
            tools_by_name=tools_by_name,
        )
        self.assertFalse(report.is_valid)
        self.assertTrue(report.has_missing_required)

    def test_validate_tool_calls_detects_unknown_tool(self) -> None:
        tools_by_name = index_tools_by_name([_tool_def("get_weather", [])])
        report = validate_tool_calls(
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "teleport_car", "arguments": "{}"},
                }
            ],
            tools_by_name=tools_by_name,
        )
        self.assertFalse(report.is_valid)
        self.assertEqual(report.unknown_tool_names, ["teleport_car"])

    def test_map_tool_results_uses_pending_call_order(self) -> None:
        pending = [
            {"id": "call_a", "function": {"name": "search_poi"}},
            {"id": "call_b", "function": {"name": "search_poi"}},
        ]
        results = [
            {"tool_name": "search_poi", "content": "result-1"},
            {"tool_name": "search_poi", "content": "result-2"},
        ]
        mapped = map_tool_results_to_history(pending, results)
        self.assertEqual(mapped[0]["tool_call_id"], "call_a")
        self.assertEqual(mapped[1]["tool_call_id"], "call_b")

    def test_should_block_unverified_completion(self) -> None:
        self.assertTrue(
            should_block_unverified_completion(
                user_text="Open the sunroof now",
                assistant_text="Done, I opened the sunroof.",
                last_tool_results=[],
            )
        )
        self.assertFalse(
            should_block_unverified_completion(
                user_text="Open the sunroof now",
                assistant_text="Done, I opened the sunroof.",
                last_tool_results=[{"tool_name": "open_sunroof", "content": "ok"}],
            )
        )
        self.assertFalse(
            should_block_unverified_completion(
                user_text="Open the sunroof now",
                assistant_text="I need your confirmation before I proceed.",
                last_tool_results=[],
            )
        )


if __name__ == "__main__":
    unittest.main()

