"""
CAR-bench Purple Agent.

Design goals for this implementation:
1. Maximize stable tool execution on base tasks.
2. Prevent fabricated abilities/actions on hallucination tasks.
3. Ask clarification before acting when required arguments are missing.
4. Keep protocol-conformant A2A responses (TextPart/DataPart tool_calls).
"""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import DataPart, Part, TextPart
from a2a.utils import new_agent_parts_message
from litellm import completion

sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_utils import configure_logger
from tool_call_types import ToolCall, ToolCallsData
sys.path.pop(0)

from agent_guardrails import (
    ERROR_HINT_RE,
    ToolValidationReport,
    build_missing_info_clarification,
    build_repair_feedback,
    build_unknown_tool_limitation,
    index_tools_by_name,
    looks_like_clarification,
    map_tool_results_to_history,
    parse_inbound,
    safe_json_loads,
    should_block_unverified_completion,
    validate_tool_calls,
)

logger = configure_logger(role="agent", context="-")

AGENT_SYSTEM_PROMPT = """You are a reliability-first in-car assistant evaluated by CAR-bench.

Operating rules:
- Never claim you executed an action unless a tool was actually called and you received a corresponding tool result.
- Never invent tools, data, contacts, locations, or outcomes.
- If information is missing for a required action, ask a focused clarification question instead of guessing.
- If the requested capability is unavailable in provided tools, clearly state the limitation and offer feasible alternatives.
- Follow all policy instructions in the benchmark system prompt strictly.
- Keep responses concise, factual, and action-oriented.
"""

MAX_MODEL_ATTEMPTS = 2
MAX_CONSECUTIVE_CLARIFICATIONS = 2


@dataclass
class ConversationState:
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    tools_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    benchmark_system_prompt: str | None = None
    last_user_text: str = ""
    last_tool_results: list[dict[str, Any]] = field(default_factory=list)
    consecutive_clarifications: int = 0
    turn_counter: int = 0


def _sanitize_tool_calls(tool_calls: list[dict[str, Any]]) -> list[ToolCall]:
    output: list[ToolCall] = []
    for tool_call in tool_calls:
        fn = tool_call.get("function", {})
        tool_name = fn.get("name", "")
        ok, parsed_arguments = safe_json_loads(fn.get("arguments", "{}"))
        if not ok or not isinstance(parsed_arguments, dict):
            parsed_arguments = {}
        output.append(ToolCall(tool_name=tool_name, arguments=parsed_arguments))
    return output


class CARBenchAgentExecutor(AgentExecutor):
    """Executor for the CAR-bench purple agent."""

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        thinking: bool = False,
        reasoning_effort: str = "medium",
        interleaved_thinking: bool = False,
        dashscope_api_key: str | None = None,
        dashscope_base_url: str | None = None,
    ):
        self.model = model
        self.temperature = temperature
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort
        self.interleaved_thinking = interleaved_thinking
        self.dashscope_api_key = dashscope_api_key
        self.dashscope_base_url = dashscope_base_url
        self.ctx_state: dict[str, ConversationState] = {}

    def _get_or_create_state(self, context_id: str) -> ConversationState:
        if context_id not in self.ctx_state:
            self.ctx_state[context_id] = ConversationState()
        return self.ctx_state[context_id]

    def _build_completion_kwargs(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
        }
        # DashScope OpenAI-compatible endpoint (for Qwen models).
        if self.dashscope_api_key and self.dashscope_base_url and "qwen" in self.model.lower():
            kwargs["api_key"] = self.dashscope_api_key
            kwargs["api_base"] = self.dashscope_base_url
        if tools:
            kwargs["tools"] = copy.deepcopy(tools)

        # DashScope Qwen OpenAI-compatible endpoint does not support reasoning_effort.
        model_lower = self.model.lower()
        is_qwen_openai_compatible = "qwen" in model_lower

        if self.thinking:
            if is_qwen_openai_compatible:
                # Keep default completion args only.
                pass
            elif self.model == "claude-opus-4-6":
                kwargs["thinking"] = {"type": "adaptive"}
            elif self.reasoning_effort in {"none", "disable", "low", "medium", "high"}:
                kwargs["reasoning_effort"] = self.reasoning_effort
            else:
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": int(self.reasoning_effort),
                }
            if self.interleaved_thinking:
                kwargs["extra_headers"] = {"anthropic-beta": "interleaved-thinking-2025-05-14"}

        return kwargs

    def _generate_candidate(
        self,
        state: ConversationState,
        repair_feedback: str | None = None,
    ) -> dict[str, Any]:
        messages = list(state.messages)
        if repair_feedback:
            messages = messages + [{"role": "user", "content": repair_feedback}]

        response = completion(
            messages=messages,
            **self._build_completion_kwargs(state.tools),
        )
        return response.choices[0].message.model_dump(exclude_unset=True)

    def _decide_response(
        self,
        state: ConversationState,
        ctx_logger: Any,
    ) -> tuple[dict[str, Any], str, int]:
        repair_feedback: str | None = None

        for attempt in range(1, MAX_MODEL_ATTEMPTS + 1):
            candidate = self._generate_candidate(state, repair_feedback=repair_feedback)
            tool_calls = candidate.get("tool_calls") or []
            report: ToolValidationReport = validate_tool_calls(tool_calls, state.tools_by_name)

            if report.is_valid:
                text = (candidate.get("content") or "").strip()
                if (
                    not tool_calls
                    and should_block_unverified_completion(
                        user_text=state.last_user_text,
                        assistant_text=text,
                        last_tool_results=state.last_tool_results,
                    )
                ):
                    return (
                        {
                            "content": (
                                "I haven't executed that action yet. "
                                "If you want me to do it, I will call the appropriate tool now."
                            )
                        },
                        "blocked_unverified_completion",
                        attempt,
                    )
                return candidate, "ok", attempt

            ctx_logger.warning(
                "Tool-call validation failed",
                validation=report.summary(),
                attempt=attempt,
            )

            if report.unknown_tool_names:
                return {"content": build_unknown_tool_limitation(report)}, "unknown_tool", attempt

            if report.has_missing_required and state.consecutive_clarifications < MAX_CONSECUTIVE_CLARIFICATIONS:
                return {"content": build_missing_info_clarification(report)}, "missing_required_clarify", attempt

            repair_feedback = build_repair_feedback(report)

        return (
            {
                "content": (
                    "I can’t safely proceed with the available information and tools. "
                    "Please clarify your request."
                )
            },
            "fallback_safe_stop",
            MAX_MODEL_ATTEMPTS,
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        ctx_logger = logger.bind(role="agent", context=f"ctx:{context.context_id[:8]}")
        state = self._get_or_create_state(context.context_id)
        state.turn_counter += 1

        parsed = parse_inbound(context.message, context.get_user_input())

        if parsed.tools is not None:
            state.tools = parsed.tools
            state.tools_by_name = index_tools_by_name(parsed.tools)

        if parsed.benchmark_system_prompt:
            if not state.messages:
                state.messages.append({"role": "system", "content": AGENT_SYSTEM_PROMPT})
                state.messages.append({"role": "system", "content": parsed.benchmark_system_prompt})
            state.benchmark_system_prompt = parsed.benchmark_system_prompt
        elif not state.messages:
            state.messages.append({"role": "system", "content": AGENT_SYSTEM_PROMPT})
            if state.benchmark_system_prompt:
                state.messages.append({"role": "system", "content": state.benchmark_system_prompt})

        inbound_kind = "empty"
        if parsed.tool_results:
            inbound_kind = "tool_results"
            state.messages.extend(
                map_tool_results_to_history(
                    pending_tool_calls=state.pending_tool_calls,
                    tool_results=parsed.tool_results,
                )
            )
            state.pending_tool_calls = []
            state.last_tool_results = parsed.tool_results
        elif parsed.user_text is not None:
            inbound_kind = "user_text"
            state.messages.append({"role": "user", "content": parsed.user_text})
            state.last_user_text = parsed.user_text
            state.last_tool_results = []
        else:
            state.messages.append({"role": "user", "content": "none"})

        ctx_logger.info(
            "Processing turn",
            turn=state.turn_counter,
            inbound_kind=inbound_kind,
            tools=len(state.tools_by_name),
            pending_tool_calls=len(state.pending_tool_calls),
        )

        try:
            assistant_content, decision_tag, attempts_used = self._decide_response(state, ctx_logger)
            assistant_text = assistant_content.get("content")
            assistant_tool_calls = assistant_content.get("tool_calls") or []
        except Exception as exc:  # noqa: BLE001
            ctx_logger.exception("Model execution failed", error=str(exc))
            assistant_text = (
                "I ran into an internal issue and couldn’t safely execute that action. "
                "Please try again."
            )
            assistant_tool_calls = []
            assistant_content = {"content": assistant_text}
            decision_tag = "llm_exception"
            attempts_used = 1

        if assistant_tool_calls:
            state.pending_tool_calls = assistant_tool_calls
            state.consecutive_clarifications = 0
        elif assistant_text and looks_like_clarification(assistant_text):
            state.consecutive_clarifications += 1
        else:
            state.consecutive_clarifications = 0

        history_entry: dict[str, Any] = {"role": "assistant", "content": assistant_text}
        if assistant_tool_calls:
            history_entry["tool_calls"] = assistant_tool_calls
        if assistant_content.get("reasoning_content"):
            history_entry["reasoning_content"] = assistant_content["reasoning_content"]
        state.messages.append(history_entry)

        parts: list[Part] = []
        if assistant_text:
            parts.append(Part(root=TextPart(kind="text", text=assistant_text)))
        if assistant_tool_calls:
            tool_calls_data = ToolCallsData(tool_calls=_sanitize_tool_calls(assistant_tool_calls))
            parts.append(Part(root=DataPart(kind="data", data=tool_calls_data.model_dump())))
        if assistant_content.get("reasoning_content"):
            parts.append(
                Part(
                    root=DataPart(
                        kind="data",
                        data={"reasoning_content": assistant_content["reasoning_content"]},
                    )
                )
            )
        if not parts:
            parts.append(Part(root=TextPart(kind="text", text="")))

        ctx_logger.info(
            "Sending response",
            decision=decision_tag,
            attempts=attempts_used,
            has_text=bool(assistant_text),
            num_tool_calls=len(assistant_tool_calls),
            clarification_streak=state.consecutive_clarifications,
        )
        if parsed.tool_results and any(ERROR_HINT_RE.search(str(tr.get("content", ""))) for tr in parsed.tool_results):
            ctx_logger.warning("Latest tool results contained error hints")

        response = new_agent_parts_message(parts=parts, context_id=context.context_id)
        await event_queue.enqueue_event(response)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.bind(role="agent", context=f"ctx:{context.context_id[:8]}").info(
            "Canceling context",
            context_id=context.context_id[:8],
        )
        self.ctx_state.pop(context.context_id, None)
