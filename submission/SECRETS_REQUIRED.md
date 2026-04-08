# Secrets Required (Leaderboard Fork)

Set these in your leaderboard fork GitHub repository secrets before submission.

## Usually required

- `GEMINI_API_KEY` (green-agent user simulator path in CAR-bench flows)
- `LOGURU_LEVEL` (optional but recommended, e.g. `INFO`)

## Provider-dependent (set only if your model path needs them)

- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `OPENAI_API_KEY`

## Notes

- Do not commit secrets to git.
- Keep `.env`, local caches, outputs, and logs out of PRs.
- Validate secret names exactly match your scenario `env` placeholders.
