"""Pure guardrail and protocol helpers for the CAR-bench purple agent."""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

ACTION_REQUEST_RE = re.compile(
    r"\b("
    r"open|close|turn on|turn off|set|adjust|increase|decrease|"
    r"navigate|route|go to|drive to|call|message|text|email|"
    r"play|stop|start|book|reserve|schedule|charge|unlock|lock|"
    r"send|share|remind|add|delete"
    r")\b",
    re.IGNORECASE,
)
COMPLETION_CLAIM_RE = re.compile(
    r"\b("
    r"done|completed|finished|i did|i have|already|sent|opened|closed|"
    r"started|stopped|set|scheduled|reserved|booked|navigating|"
    r"on it now|it is now"
    r")\b",
    re.IGNORECASE,
)
LIMITATION_TEXT_RE = re.compile(
    r"\b("
    r"cannot|can't|unable|not available|unsupported|don't have access|"
    r"need more information|please provide|clarify"
    r")\b",
    re.IGNORECASE,
)
ERROR_HINT_RE = re.compile(
    r"\b(error|failed|not found|unavailable|unsupported|invalid|denied)\b",
    re.IGNORECASE,
)


@dataclass
class ParsedInbound:
    user_text: str | None = None
    benchmark_system_prompt: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ToolValidationIssue:
    kind: str
    tool_name: str
    detail: str
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class ToolValidationReport:
    issues: list[ToolValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues

    @property
    def unknown_tool_names(self) -> list[str]:
        return sorted({issue.tool_name for issue in self.issues if issue.kind == "unknown_tool"})

    @property
    def has_missing_required(self) -> bool:
        return any(issue.kind == "missing_required" for issue in self.issues)

    def missing_required_issues(self) -> list[ToolValidationIssue]:
        return [issue for issue in self.issues if issue.kind == "missing_required"]

    def summary(self) -> str:
        if not self.issues:
            return "ok"
        return "; ".join(f"{issue.kind}:{issue.tool_name}:{issue.detail}" for issue in self.issues)


def safe_json_loads(value: Any) -> tuple[bool, Any]:
    if isinstance(value, dict):
        return True, value
    if value is None:
        return True, {}
    if not isinstance(value, str):
        return False, None
    try:
        return True, json.loads(value)
    except json.JSONDecodeError:
        return False, None


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def index_tools_by_name(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for tool in tools:
        fn = tool.get("function", {})
        name = fn.get("name")
        if isinstance(name, str) and name:
            indexed[name] = tool
    return indexed


def _required_fields_for_tool(tool_def: dict[str, Any]) -> list[str]:
    params = tool_def.get("function", {}).get("parameters", {})
    required = params.get("required", [])
    if isinstance(required, list):
        return [field for field in required if isinstance(field, str)]
    return []


def validate_tool_calls(
    tool_calls: list[dict[str, Any]],
    tools_by_name: dict[str, dict[str, Any]],
) -> ToolValidationReport:
    report = ToolValidationReport()
    for tool_call in tool_calls:
        fn = tool_call.get("function", {})
        tool_name = fn.get("name", "")
        raw_arguments = fn.get("arguments", "{}")
        ok, parsed_arguments = safe_json_loads(raw_arguments)

        if tool_name not in tools_by_name:
            report.issues.append(
                ToolValidationIssue(
                    kind="unknown_tool",
                    tool_name=tool_name or "<missing>",
                    detail="tool not in provided tool list",
                )
            )
            continue

        if not ok or not isinstance(parsed_arguments, dict):
            report.issues.append(
                ToolValidationIssue(
                    kind="invalid_json",
                    tool_name=tool_name,
                    detail="arguments must be valid JSON object",
                )
            )
            continue

        missing_fields = [
            field_name
            for field_name in _required_fields_for_tool(tools_by_name[tool_name])
            if _is_missing(parsed_arguments.get(field_name))
        ]
        if missing_fields:
            report.issues.append(
                ToolValidationIssue(
                    kind="missing_required",
                    tool_name=tool_name,
                    detail=f"missing required fields: {', '.join(missing_fields)}",
                    missing_fields=missing_fields,
                )
            )

    return report


def map_tool_results_to_history(
    pending_tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_name: dict[str, deque[dict[str, Any]]] = {}
    for tool_call in pending_tool_calls:
        name = tool_call.get("function", {}).get("name", "")
        by_name.setdefault(name, deque()).append(tool_call)

    history_entries: list[dict[str, Any]] = []
    for idx, result in enumerate(tool_results):
        tool_name = result.get("tool_name", "")
        pending_for_name = by_name.get(tool_name, deque())
        call_id = result.get("tool_call_id", "")
        if pending_for_name:
            call_id = pending_for_name.popleft().get("id", call_id)

        if not call_id:
            call_id = f"orphan_tool_result_{idx}"

        history_entries.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": result.get("content", ""),
            }
        )
    return history_entries


def should_block_unverified_completion(
    user_text: str,
    assistant_text: str,
    last_tool_results: list[dict[str, Any]],
) -> bool:
    if not user_text or not assistant_text:
        return False
    if not ACTION_REQUEST_RE.search(user_text):
        return False
    if last_tool_results:
        return False
    if not COMPLETION_CLAIM_RE.search(assistant_text):
        return False
    if LIMITATION_TEXT_RE.search(assistant_text):
        return False
    if "?" in assistant_text:
        return False
    return True


def parse_inbound(message: Any, fallback_text: str | None) -> ParsedInbound:
    parsed = ParsedInbound()

    for part in getattr(message, "parts", []):
        root = getattr(part, "root", part)
        kind = getattr(root, "kind", None)
        if kind == "text":
            text = (getattr(root, "text", "") or "").strip()
            if "System:" in text and "\n\nUser:" in text:
                system_part, user_part = text.split("\n\nUser:", 1)
                parsed.benchmark_system_prompt = system_part.replace("System:", "", 1).strip()
                parsed.user_text = user_part.strip()
            elif text:
                parsed.user_text = text
        elif kind == "data":
            raw_data = getattr(root, "data", {})
            data = raw_data if isinstance(raw_data, dict) else {}
            if "tools" in data and isinstance(data["tools"], list):
                parsed.tools = data["tools"]
            if "tool_results" in data and isinstance(data["tool_results"], list):
                parsed.tool_results = data["tool_results"]

    if not parsed.user_text and not parsed.tool_results and fallback_text:
        parsed.user_text = fallback_text

    return parsed


def build_missing_info_clarification(report: ToolValidationReport) -> str:
    issue = report.missing_required_issues()[0]
    fields = ", ".join(issue.missing_fields)
    return (
        f"Before I can run `{issue.tool_name}`, I still need: {fields}. "
        "Please provide that detail."
    )


def build_unknown_tool_limitation(report: ToolValidationReport) -> str:
    names = ", ".join(report.unknown_tool_names)
    return (
        "I can't execute that directly because the required capability is not available "
        f"in the current tool set ({names}). I can continue with supported tools if you want."
    )


def build_repair_feedback(report: ToolValidationReport) -> str:
    lines = [
        "Your previous response violated execution constraints.",
        "Fix it and return a corrected assistant response.",
        "Constraints:",
        "- Use only provided tools.",
        "- Arguments must be valid JSON.",
        "- Include all required tool parameters.",
        f"Issues found: {report.summary()}",
    ]
    return "\n".join(lines)


def looks_like_clarification(text: str) -> bool:
    text_lower = text.lower()
    return (
        "?" in text
        or "please provide" in text_lower
        or "could you" in text_lower
        or "which " in text_lower
        or "what " in text_lower
        or "need" in text_lower
    )
