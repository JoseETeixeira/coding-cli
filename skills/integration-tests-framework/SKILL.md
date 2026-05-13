---
name: integration-tests-framework
description: Runs and debugs Python integration tests using LocalStack, Redis, docker compose, and pytest. Use when the user asks to run integration tests, worker-backed integration tests, start/stop test infrastructure, or troubleshoot LocalStack/Redis test failures.
---

# Integration Tests Framework

## Quick Start

Use these defaults:

1. Check Docker availability: `docker ps`
2. Start infrastructure: `make local-infra`
3. Run targeted tests with `poetry run pytest ... -v`
4. Stop infrastructure when finished: `make local-down`

## When to Use This Skill

Apply this skill when work involves:

- `tests/integration/`
- LocalStack on `http://localhost:4566`
- Redis on `localhost:6379`
- `docker-compose.local.yml`
- `scripts/run_integration_tests.sh`
- `scripts/run_worker_integration_tests.sh`

## Infrastructure Commands

Preferred commands:

- Infra only: `make local-infra`
- Full local stack: `make local-up`
- Stop and clean volumes: `make local-down`
- Stream logs: `make local-logs`

Direct compose equivalents:

- `docker compose -f docker-compose.local.yml up -d redis localstack localstack-init`
- `docker compose -f docker-compose.local.yml down -v --remove-orphans`

Worker-backed stack:

- `docker compose -f docker-compose.local.yml -f docker-compose.worker-integration.override.yml up -d --build redis localstack localstack-init stub-backend api worker`

## Test Execution Paths

### Path A: Repo integration tests (default)

For most current integration tests:

1. Ensure LocalStack/Redis are running.
2. Reset/seed tables:
   - `python scripts/init_localstack.py --endpoint http://localhost:4566 --reset --seed`
3. Run tests:
   - `poetry run pytest tests/integration/ -v`
4. For a focused module, run the specific file path.

### Path B: Scripted integration flow

Use the script when full setup/teardown behavior is desired:

- `./scripts/run_integration_tests.sh`
- Keep infra alive: `./scripts/run_integration_tests.sh --keep-infra`
- Reuse already-running infra: `./scripts/run_integration_tests.sh --no-infra`

### Path C: Worker-backed flow

Use when validating API+worker container behavior:

- `./scripts/run_worker_integration_tests.sh`
- Keep infra alive: `./scripts/run_worker_integration_tests.sh --keep-infra`

Note: script default target is `tests/integration_worker/`; if the requested tests live under `tests/integration/`, run `poetry run pytest` directly with exact file paths.

## Health Checks and Debugging

Run these checks before blaming tests:

1. Docker daemon reachable: `docker ps`
2. LocalStack health: `curl -sf http://localhost:4566/_localstack/health`
3. Redis health:
   - `docker compose -f docker-compose.local.yml exec -T redis redis-cli ping`
4. API health (if running full stack): `curl -sf http://localhost:8000/health`

If LocalStack connection errors appear (`Could not connect to the endpoint URL`):

- Start infra (`make local-infra`)
- Re-run `scripts/init_localstack.py --reset --seed`
- Re-run the failing pytest command

If container startup fails:

- Inspect status: `docker ps -a`
- Inspect logs: `docker compose -f docker-compose.local.yml logs --no-color`

## Output Expectations

When reporting results:

- State exact command run
- Report pass/fail counts
- Include the first actionable failure cause
- Call out infra precondition issues separately (e.g., Docker stopped, LocalStack down)

## Additional Resources

- Common runbooks: [examples.md](examples.md)
