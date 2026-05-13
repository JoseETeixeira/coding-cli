# Integration Test Examples

## 1) Run tracking disambiguation integration tests

```bash
make local-infra
poetry run pytest tests/integration/graphs/tracking_data/test_tracking_disambiguation_integration.py tests/integration/workers/test_tracking_data_disambiguation_worker_integration.py -v
```

## 2) Run one integration test file (LocalStack only)

Use when validating a single module under `tests/integration/`.

```bash
make local-infra
python scripts/init_localstack.py --endpoint http://localhost:4566 --reset --seed
poetry run pytest tests/integration/graphs/tracking_data/test_tracking_disambiguation_integration.py -v
make local-down
```

## 3) Run targeted integration tests and keep infra up

Use when iterating on failures across multiple runs.

```bash
./scripts/run_integration_tests.sh --keep-infra -k "disambiguation"
```

Then re-run quickly:

```bash
./scripts/run_integration_tests.sh --no-infra -k "disambiguation"
```

## 4) Run worker-backed integration suite

Use when validating API + worker container interactions.

```bash
./scripts/run_worker_integration_tests.sh
```

Keep stack running for debugging:

```bash
./scripts/run_worker_integration_tests.sh --keep-infra
docker compose -f docker-compose.local.yml -f docker-compose.worker-integration.override.yml logs --no-color
```
