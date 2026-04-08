# CAR-bench Leaderboard Submission Guide

This repository prepares your purple agent for CAR-bench leaderboard submission. Browser-only actions are manual and cannot be automated here.

## 1. Build and publish your purple image

```bash
make docker-build IMAGE=ghcr.io/<your-org-or-user>/<repo>-purple-agent:<tag>
make docker-push IMAGE=ghcr.io/<your-org-or-user>/<repo>-purple-agent:<tag>
```

Use `linux/amd64` images for leaderboard compatibility.

## 2. Register or update your AgentBeats agent

Manual on https://agentbeats.dev:

1. Create/update the purple agent entry.
2. Point it to your published GHCR image.
3. Copy the resulting `AGENTBEATS_ID`.

## 3. Prepare leaderboard fork

1. Fork `CAR-bench/car-bench-leaderboard-agentbeats`.
2. Create a non-default branch in your fork.
3. Add required GitHub Secrets in your fork (see `submission/SECRETS_REQUIRED.md`).

## 4. Edit leaderboard `scenario.toml`

Start from `submission/scenario.example.toml` in this repo and copy it into your leaderboard fork as `scenario.toml`.

Fill these placeholders manually:

- `AGENTBEATS_ID`
- model name (`AGENT_LLM`)
- provider-specific env vars/secrets

Use full-submission settings exactly:

- `num_trials = 3`
- `task_split = "test"`
- `tasks_base_num_tasks = -1`
- `tasks_hallucination_num_tasks = -1`
- `tasks_disambiguation_num_tasks = -1`
- `max_steps = 50`

## 5. Commit and open PR

1. Commit `scenario.toml` and any required metadata in your leaderboard fork branch.
2. Push branch and open PR to leaderboard repo.
3. Monitor Actions logs and leaderboard maintainers' feedback.

## Cost and workflow warning

Editing and committing `scenario.toml` in the leaderboard fork can trigger evaluation workflows and may incur model/API cost. Verify all placeholders, secrets, and task settings before pushing.
