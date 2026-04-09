IMAGE ?= ghcr.io/your-github-username/your-repo-purple-agent:latest

.PHONY: help run-local test docker-build docker-run docker-push

help:
	@echo "Targets:"
	@echo "  run-local     Run purple agent server on localhost:8080"
	@echo "  test          Run unit/smoke tests"
	@echo "  docker-build  Build purple agent image (linux/amd64)"
	@echo "  docker-run    Run purple agent container with .env"
	@echo "  docker-push   Push IMAGE to registry"

run-local:
	uv run src/purple_car_bench_agent/server.py --host 127.0.0.1 --port 8080

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

docker-build:
	docker build --platform linux/amd64 -f src/purple_car_bench_agent/Dockerfile.car-bench-agent -t $(IMAGE) .

docker-run:
	docker run --rm -p 8080:8080 --env-file .env $(IMAGE) --host 0.0.0.0 --port 8080

docker-push:
	docker push $(IMAGE)
