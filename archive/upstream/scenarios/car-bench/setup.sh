#!/bin/bash
# Setup script for CAR-bench scenario
# This clones the car-bench code required to run the benchmark

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAR_BENCH_DIR="$SCRIPT_DIR/car-bench"
PYPROJECT_PATH="$CAR_BENCH_DIR/pyproject.toml"

if [ -d "$CAR_BENCH_DIR" ]; then
    if [ -f "$PYPROJECT_PATH" ]; then
        echo "car-bench already exists at $CAR_BENCH_DIR"
        echo "To re-download, remove the directory first: rm -rf $CAR_BENCH_DIR"
        exit 0
    fi

    echo "Found incomplete car-bench directory at $CAR_BENCH_DIR (missing pyproject.toml)."
    echo "Removing and re-cloning..."
    rm -rf "$CAR_BENCH_DIR"
fi

echo "Cloning car-bench repository..."
git clone --depth 1 https://github.com/CAR-bench/car-bench.git "$CAR_BENCH_DIR"


echo ""
echo "✅ Setup complete! car-bench is ready at:"
echo "   $CAR_BENCH_DIR"
echo ""
echo "📝 Note: Tasks and mock data are automatically loaded from HuggingFace"
echo ""
echo "🚀 Next steps:"
echo "   1. Install dependencies: uv sync --extra car-bench-agent --extra car-bench-evaluator"
echo "   2. Run the scenario: uv run agentbeats-run scenarios/scenario.toml --show-logs"
