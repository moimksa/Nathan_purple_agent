# Submission Checklist

- [ ] Purple image builds locally for `linux/amd64`.
- [ ] Purple image is published to GHCR and accessible.
- [ ] Agent registered/updated on AgentBeats.
- [ ] `AGENTBEATS_ID` copied correctly.
- [ ] Leaderboard fork created.
- [ ] Work is on a non-default branch in leaderboard fork.
- [ ] Required GitHub Secrets configured (see `SECRETS_REQUIRED.md`).
- [ ] `scenario.toml` copied from `scenario.example.toml` and placeholders replaced.
- [ ] Full-submission config is set exactly:
  - [ ] `num_trials = 3`
  - [ ] `task_split = "test"`
  - [ ] `tasks_base_num_tasks = -1`
  - [ ] `tasks_hallucination_num_tasks = -1`
  - [ ] `tasks_disambiguation_num_tasks = -1`
  - [ ] `max_steps = 50`
- [ ] You understand committing `scenario.toml` can trigger evaluation workflows and cost.
- [ ] Submission PR opened to leaderboard repository.
