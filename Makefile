# DocTranslate — Makefile
# Convenient commands for local development and testing

.PHONY: help venv install test run clean docker-build deploy-check

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv:  ## Create Python virtual environment
	python3 -m venv .venv
	@echo "Created .venv/ — activate with: source .venv/bin/activate"

install: .venv/bin/python  ## Install Python dependencies
	.venv/bin/pip install --quiet --upgrade pip
	.venv/bin/pip install --quiet -r requirements.txt
	@echo "Dependencies installed"

test:  ## Run all tests
	.venv/bin/pytest tests/ -v --tb=short

test-quick:  ## Run tests (quiet, 5s timeout per test)
	.venv/bin/pytest tests/ -q --tb=short --timeout=5

run:  ## Start dev server (reload on changes)
	.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000 --reload

run-docker:  ## Build and run with Docker
	docker build -t doc-translate .
	docker run --rm -p 8000:8000 -e PORT=8000 doc-translate

clean:  ## Remove caches and artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/ 2>/dev/null || true
	@echo "Cleanup complete"

deploy-check:  ## Verify everything needed before deploy
	@echo "=== Pre-deploy checks ==="
	@echo -n "Tests... "
	@.venv/bin/pytest tests/ -q --tb=short 2>&1 | tail -1
	@echo -n "Docker build... "
	@docker build -q -t doc-translate . 2>&1 && echo "OK" || echo "FAIL"
	@echo -n "Requirements up to date... "
	@.venv/bin/pip install --dry-run -r requirements.txt -q 2>&1 | grep -c "Would install" || echo "yes"
	@echo "=== Done ==="

.env:  ## Copy .env.example to .env if not exists (safe)
	@test -f .env || cp .env.example .env && echo "Created .env from .env.example"
	@ls -la .env 2>/dev/null || echo "WARNING: .env already exists, skipping"
