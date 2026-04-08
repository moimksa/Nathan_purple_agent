# AGENTS

## Purple Agent

- Name: `car_bench_agent`
- Entry point: `src/purple_car_bench_agent/server.py`
- Default local endpoint: `http://127.0.0.1:8080`
- Agent card endpoint: `/.well-known/agent-card.json`

## Runtime Inputs

The agent receives A2A messages containing:

- `TextPart`: system prompt and user utterances
- `DataPart`: tool definitions and tool results

The agent returns:

- `TextPart`: concise user-facing response
- `DataPart`: `tool_calls` payload when actions are needed

## Guardrails

Core reliability controls are implemented in `src/purple_car_bench_agent/agent_guardrails.py`:

- reject unknown tools
- reject invalid tool-call JSON
- detect missing required tool arguments and request clarification
- block unverified completion claims

## Environment Variables

- `AGENT_LLM`
- `AGENT_TEMPERATURE`
- `AGENT_REASONING_EFFORT`
- `AGENT_THINKING`
- `AGENT_INTERLEAVED_THINKING`
- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `LOGURU_LEVEL`

## Testing

```bash
make test
```
