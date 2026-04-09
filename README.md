# A2A Computer-Use Agent

This repository contains an A2A-compatible computer-use / web agent implementation.  
The agent is not scoped to a single benchmark; CAR-bench, OSWorld-Verified, and related submission materials are included only as evaluation or integration contexts.
The active runtime entry point is `src/purple_car_bench_agent/server.py`, exposing an agent card at `/.well-known/agent-card.json`.

## Repository Focus

- A2A agent server and executor logic under `src/purple_car_bench_agent/`
- Guardrail utilities for tool-call safety and reliability checks
- Local run, test, and Docker build workflow
- Optional benchmark/submission helper docs under `submission/`

## Requirements

- Python `3.11+`
- `uv`
- Docker (optional, for container build/run)
- Model provider API keys (based on your `AGENT_LLM`)

## Local Setup

```bash
cp .env.example .env
# edit .env
uv sync
```

## Run Locally

```bash
make run-local
```

Default endpoint:

- `http://127.0.0.1:8080`

Validate the agent card:

```bash
curl http://127.0.0.1:8080/.well-known/agent-card.json
```

## Test

```bash
make test
```

## Docker

Build:

```bash
make docker-build IMAGE=ghcr.io/<org-or-user>/<repo>-purple-agent:latest
```

Run:

```bash
make docker-run IMAGE=ghcr.io/<org-or-user>/<repo>-purple-agent:latest
```

Publish:

```bash
make docker-push IMAGE=ghcr.io/<org-or-user>/<repo>-purple-agent:latest
```

CI workflow: `.github/workflows/publish-purple.yml` (test, build, and push `linux/amd64` image).

## Agent Card and Runtime Notes

- Agent name: `car_bench_agent`
- Entry point: `src/purple_car_bench_agent/server.py`
- Runtime and input/output expectations: `AGENTS.md`

## Optional Evaluation and Submission Notes

- Guide: `SUBMIT_CARBENCH.md`
- Templates/checklists: `submission/`

These files are supporting material and do not define the repository's primary identity.

## Local-Only / Archived Materials

Some upstream benchmark/evaluator assets may be kept locally for reference, but are excluded from Git tracking and Docker build context by ignore rules.

## License and Attribution

- License: `LICENSE`
- Attribution: `docs/ATTRIBUTION.md`
