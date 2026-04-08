# CAR-bench Purple Agent (AgentBeats Submission Repo)

This repository is a submission-focused version of `car-bench-agentbeats`, narrowed to the **purple agent** (agent under test) for the AgentX-AgentBeats CAR-bench competition.

## Scope

Active code in this repo focuses on:

- Purple agent logic: `src/purple_car_bench_agent/`
- Purple agent runtime and image build
- Submission documentation and templates
- Minimal tests for guardrail behavior

Benchmark runner / green-agent infrastructure from upstream has been preserved under `archive/upstream/` for traceability, but is not the active submission path.

## What Is Different From Upstream

Compared with the upstream benchmark-oriented repository:

- Active repo paths are purple-agent-centric.
- Green-agent/evaluator and scenario orchestration files were moved to `archive/upstream/`.
- Docker and CI are focused on publishing one purple image.
- Submission helper files were added under `submission/`.
- Documentation now targets CAR-bench leaderboard submission flow.

## Requirements

- Python `3.11+`
- `uv` package manager
- Docker (for image build/run)
- API credentials for your selected model provider

## Local Setup

```bash
cp .env.example .env
# Edit .env with your model/provider keys and AGENT_LLM

uv sync
```

## Run Purple Agent Locally

```bash
make run-local
# or:
uv run src/purple_car_bench_agent/server.py --host 127.0.0.1 --port 8080
```

Validate the agent card endpoint:

```bash
curl http://127.0.0.1:8080/.well-known/agent-card.json
```

## Build Docker Image (linux/amd64)

```bash
make docker-build IMAGE=ghcr.io/<your-org-or-user>/<repo>-purple-agent:latest
```

Run the container locally:

```bash
make docker-run IMAGE=ghcr.io/<your-org-or-user>/<repo>-purple-agent:latest
```

## Publish Image

Option A: local docker push

```bash
make docker-push IMAGE=ghcr.io/<your-org-or-user>/<repo>-purple-agent:latest
```

Option B: GitHub Actions workflow

- Use `.github/workflows/publish-purple.yml`
- Builds and publishes `linux/amd64` image

## Tests

```bash
make test
```

## Submission Files

- `SUBMIT_CARBENCH.md`
- `ABSTRACT.md`
- `AGENTS.md`
- `submission/scenario.example.toml`
- `submission/SECRETS_REQUIRED.md`
- `submission/CHECKLIST.md`
- `submission/PR_TEMPLATE_CARBENCH.md`

## Manual Steps You Still Must Do

This repo cannot perform website/browser actions for you. You still need to:

1. Register/update your purple agent on AgentBeats and get your `AGENTBEATS_ID`.
2. Configure secrets in your leaderboard-fork GitHub repository.
3. Edit leaderboard `scenario.toml` with your IDs/model/env settings.
4. Commit on a non-default branch in your fork and open the submission PR.

See `SUBMIT_CARBENCH.md` and `submission/CHECKLIST.md` for exact steps.

## License and Attribution

- This repo keeps the upstream `LICENSE`.
- Attribution notes and archived upstream materials are in `docs/ATTRIBUTION.md` and `archive/upstream/`.
