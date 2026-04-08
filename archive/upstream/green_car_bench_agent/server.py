"""Server entry point for CAR-bench evaluator agent."""
import argparse
import asyncio
import os
import sys
from pathlib import Path
import warnings

import uvicorn

# Suppress Pydantic serialization warnings from litellm types
# These occur because litellm's Message/Choices types don't set all optional fields
warnings.filterwarnings(
    "ignore",
    message=".*Pydantic serializer warnings.*",
    category=UserWarning,
    module="pydantic.main"
)

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agentbeats.green_executor import GreenExecutor
from car_bench_evaluator import CARBenchEvaluator

sys.path.insert(0, str(Path(__file__).parent.parent))
from logging_utils import configure_logger
sys.path.pop(0)

logger = configure_logger(role="evaluator", context="server")
HF_DATASET_REPO_ID = "johanneskirmayr/car-bench-dataset"
HF_ALLOW_PATTERNS = ["mock_data/**"]


def _is_valid_mock_data_dir(path: Path) -> bool:
    """Check whether path looks like a ready-to-use car-bench mock_data directory."""
    required_files = [
        path / "navigation" / "locations.jsonl",
        path / "navigation" / "weather.jsonl",
        path / "navigation" / "routes_metadata.jsonl",
        path / "navigation" / "routes_index.jsonl",
        path / "productivity_and_communication" / "contacts.jsonl",
        path / "productivity_and_communication" / "calendars.jsonl",
    ]
    return all(p.exists() for p in required_files)


def _warmup_hf_mock_data() -> None:
    """Pre-download mock_data with retries/fallback endpoint for local reliability."""
    from huggingface_hub import snapshot_download

    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")

    configured_endpoint = os.getenv("HF_ENDPOINT")
    endpoints_to_try = []
    if configured_endpoint:
        endpoints_to_try.append(configured_endpoint)
    endpoints_to_try.extend(["https://huggingface.co", "https://hf-mirror.com"])

    # Keep order and deduplicate
    deduped = []
    for endpoint in endpoints_to_try:
        if endpoint not in deduped:
            deduped.append(endpoint)

    last_error: Exception | None = None
    for endpoint in deduped:
        os.environ["HF_ENDPOINT"] = endpoint
        try:
            local_dir = snapshot_download(
                repo_id=HF_DATASET_REPO_ID,
                repo_type="dataset",
                allow_patterns=HF_ALLOW_PATTERNS,
            )
            logger.info(
                "HF mock data warmup succeeded",
                hf_endpoint=endpoint,
                cache_dir=local_dir,
            )
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "HF mock data warmup failed on endpoint",
                hf_endpoint=endpoint,
                error=str(exc),
            )

    logger.warning(
        "HF mock data warmup failed on all endpoints; runtime may fail when tasks start",
        last_error=str(last_error) if last_error else "unknown",
    )


def car_bench_evaluator_agent_card(name: str, url: str) -> AgentCard:
    """Create the agent card for the CAR-bench evaluator."""
    skill = AgentSkill(
        id="car_bench_evaluation",
        name="CAR-bench Evaluation",
        description="Evaluates agents on CAR-bench voice assistant tasks",
        tags=["benchmark", "evaluation", "car-bench"],
        examples=[
            '{"participants": {"agent": "http://localhost:8080"}, "config": {"num_tasks": 3}}'
        ],
    )
    return AgentCard(
        name=name,
        description="CAR-bench evaluator - tests agents on in-car voice assistant tasks",
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


async def main():
    parser = argparse.ArgumentParser(description="Run the CAR-bench evaluator agent.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind the server")
    parser.add_argument("--card-url", type=str, help="External URL for the agent card")
    args = parser.parse_args()

    # Map DashScope OpenAI-compatible credentials for car-bench user/policy LLM calls.
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    dashscope_base_url = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    if dashscope_key:
        # setdefault does not handle empty-string values. We want DashScope creds to
        # fill missing/empty OPENAI-compatible vars used by LiteLLM user/policy calls.
        if not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = dashscope_key
        if not os.getenv("OPENAI_API_BASE"):
            os.environ["OPENAI_API_BASE"] = dashscope_base_url

    # Keep HuggingFace cache in project-writable directory for local runs.
    project_root = Path(__file__).parent.parent.parent
    hf_home = project_root / ".cache" / "huggingface"
    hf_hub_cache = hf_home / "hub"
    hf_hub_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HF_HUB_CACHE", str(hf_hub_cache))

    # Improve HF network robustness for dataset download in local environments.
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    # Auto-configure CAR_BENCH_DATA_DIR only when it points to ready jsonl data.
    if "CAR_BENCH_DATA_DIR" not in os.environ:
        local_reference_data_dir = (
            project_root
            / "scenarios"
            / "car-bench"
            / "car-bench"
            / "docs"
            / "reference_data"
            / "mock_data"
        )
        if _is_valid_mock_data_dir(local_reference_data_dir):
            os.environ["CAR_BENCH_DATA_DIR"] = str(local_reference_data_dir)
            logger.info(f"Auto-configured CAR_BENCH_DATA_DIR={local_reference_data_dir}")

    # Optional warmup download from HuggingFace for local runs.
    # Disabled by default to avoid delaying server startup/health checks.
    if os.getenv("CAR_BENCH_ENABLE_HF_WARMUP", "false").lower() == "true":
        _warmup_hf_mock_data()

    agent_url = args.card_url or f"http://{args.host}:{args.port}/"

    logger.info(
        "Starting CAR-bench evaluator server",
        host=args.host,
        port=args.port,
        url=agent_url
    )

    agent = CARBenchEvaluator()
    executor = GreenExecutor(agent)
    agent_card = car_bench_evaluator_agent_card("CARBenchEvaluator", agent_url)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn_config = uvicorn.Config(server.build(), host=args.host, port=args.port)
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


if __name__ == "__main__":
    asyncio.run(main())
