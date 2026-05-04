---
name: console-testing-scenarios
description: Navigate and work with the Console Testing Scenarios web application. Use when maintaining, updating, refactoring, or implementing new features in the console-testing-scenarios project, including the React frontend, Flask API, or infrastructure.
---

# Console Testing Scenarios - Technical Guide

## Quick Reference

| Component | Path | Tech Stack |
|-----------|------|------------|
| Frontend | `console-testing-scenarios/freight-hero-console/` | React 18, TypeScript, Vite, Tailwind, shadcn/ui |
| Backend API | `console-testing-scenarios/console_api.py` | Flask, LangSmith SDK, boto3 |
| Infrastructure | `console-testing-scenarios/infra/` | Terraform, AWS EC2, ECR |
| Documentation | `console-testing-scenarios/docs/` | Markdown docs |

## Project Purpose

Web interface for running and evaluating AI Watchtower deep-agent test scenarios:
- Browse/select LangSmith datasets
- Execute scenarios with real-time log streaming
- Review agent reasoning feedback (thumbs up/down)

## Architecture Overview

```
Browser (React :5173)
    │
    ├── HTTP/SSE ──→ Flask API (:5001)
    │                    │
    │                    ├── LangSmith SDK (datasets, experiments, traces)
    │                    ├── RDS Data API (Aurora Serverless - feedback data)
    │                    └── DeepAgents Framework (run_evaluation, run_runs)
```

## Frontend Structure

### Directory Layout

```
freight-hero-console/src/
├── App.tsx              # Routes & providers
├── main.tsx             # Entry point
├── contexts/
│   └── AuthContext.tsx  # Auth state (bypassed by default)
├── components/
│   ├── layout/
│   │   ├── DashboardLayout.tsx  # Main layout wrapper
│   │   └── Sidebar.tsx          # Navigation sidebar
│   └── ui/                      # shadcn/ui components (~50 files)
├── pages/
│   ├── Dashboard.tsx    # Test execution runner (main feature)
│   ├── Evaluator.tsx    # Feedback review table
│   ├── Scenarios.tsx    # Coming soon placeholder
│   ├── Login.tsx        # Auth page
│   ├── Index.tsx        # Landing/redirect
│   └── NotFound.tsx     # 404 page
├── hooks/
│   ├── use-mobile.tsx   # Mobile detection
│   └── use-toast.ts     # Toast notifications
└── data/
    └── mockData.ts      # Mock data for development
```

### Routes

| Path | Component | Protected | Purpose |
|------|-----------|-----------|---------|
| `/` | Index | No | Landing/redirect |
| `/login` | Login | No | Authentication |
| `/dashboard` | Dashboard | Yes | Scenario execution UI |
| `/results` | TestResults | Yes | Scenario run history + stage grid + transcript |
| `/evaluator` | Evaluator | Yes | Feedback review |
| `/scenarios` | Scenarios | Yes | Coming soon |

### Key Patterns

**API Base URL**: Configured via `VITE_API_BASE` env var (default: `http://localhost:5001`)

```typescript
const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:5001").replace(/\/$/, "");
```

**Data Fetching**: Uses native `fetch` with `useEffect` or callbacks (not React Query for API calls)

**State Management**: React `useState` hooks - no global state library

**SSE for Logs**: `EventSource` API for real-time log streaming from `/sse/log-tail`

**UI Components**: shadcn/ui (Radix primitives + Tailwind) - all in `src/components/ui/`

## Backend API

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/datasets` | List LangSmith datasets |
| GET | `/datasets/<id>/examples` | List example IDs in dataset |
| GET | `/datasets-with-examples` | Batch fetch datasets + examples |
| POST | `/run-scenario` | Execute scenario evaluations |
| GET | `/sse/log-tail` | Stream logs via SSE |
| POST | `/api/scenario-events` | Ingest Scenario events (Results) |
| GET | `/scenario-runs` | List run history (Results) |
| DELETE | `/scenario-runs/<id>` | Delete a run and all its data |
| GET | `/scenario-runs/<id>/stages` | List stage boxes (Results) |
| GET | `/scenario-runs/<id>/stages/<scenarioRunId>` | Stage details + transcript (Results) |
| GET | `/sse/scenario-events` | Stream Scenario events via SSE (Results) |
| GET | `/api/langsmith-config` | Org/project IDs for building LangSmith trace URLs |
| GET | `/api/langsmith-trace` | Resolve LangSmith root run id for a stage (`thread_id`, `stage_index`, `num_stages`) |
| GET | `/reasonings/ratings` | Fetch feedback from Aurora DB |

### Key Integrations

**LangSmith**: Dataset storage, experiment tracking, trace visualization

```python
_langsmith_client = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))
```

**DeepAgents Framework**: Imports from `tests/deep_agents/workflow/confirm_delivery/`

```python
from tests.deep_agents.workflow.confirm_delivery.run_scenario_across_dataset import (
    run_evaluation,
    run_runs,
)
```

**AWS RDS Data API**: Aurora Serverless for feedback data

```python
_rds_data_client = session.client("rds-data", region_name=_AWS_REGION)
```

### Configuration (Environment Variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGCHAIN_API_KEY` | (required) | LangSmith authentication |
| `AWS_PROFILE` | `freighthero` | AWS credentials profile |
| `AWS_REGION` | `us-east-1` | AWS region |
| `LOG_TAIL_BYTES` | `4000` | Initial SSE log chunk size |
| `LANGSMITH_ORG_ID` | (optional) | LangSmith org UUID for trace deep links |
| `LANGSMITH_PROJECT_ID` | (optional) | LangSmith project UUID for trace deep links |
| `LANGCHAIN_PROJECT` / `LANGSMITH_PROJECT` | (optional) | LangSmith project name for trace resolution; default `scenario-framework` |

## Common Tasks

### Adding a New Page

1. Create component in `freight-hero-console/src/pages/NewPage.tsx`
2. Add route in `App.tsx` (wrap with `<ProtectedRoute>` if needed)
3. Add nav item in `Sidebar.tsx` navigation array

### Adding a New API Endpoint

1. Add route handler in `console_api.py` using Flask decorators
2. Handle CORS automatically (before/after request hooks)
3. Return consistent JSON: `{"status": "ok|error", ...}`

### Adding UI Components

Use shadcn/ui CLI or copy from existing components in `src/components/ui/`:

```bash
cd freight-hero-console
npx shadcn@latest add [component-name]
```

### Running Locally

**Docker (recommended)**:
```bash
cd console-testing-scenarios
./restart_docker_local.sh
```

**Without Docker**:
```bash
# API (from project root)
FLASK_APP=console-testing-scenarios/console_api.py flask run --port 5001

# Frontend
cd console-testing-scenarios/freight-hero-console
npm install && npm run dev
```

## File Reference Quick Lookup

| When you need to... | Look at... |
|---------------------|------------|
| Add/modify routes | `App.tsx` |
| Change navigation | `Sidebar.tsx` |
| Modify scenario execution UI | `Dashboard.tsx` |
| Modify feedback review UI | `Evaluator.tsx` |
| Add new API endpoint | `console_api.py` |
| LangSmith trace resolution / config | `console_api.py` |
| Stage details + LangSmith cache | `TestResults.tsx` |
| Change page layout | `DashboardLayout.tsx` |
| Modify auth behavior | `AuthContext.tsx` |
| Add UI components | `src/components/ui/` |
| Configure Terraform | `infra/*.tf` |
| Understand architecture | `docs/02-architecture.md` |

## Additional Resources

For detailed information, see:
- [reference.md](reference.md) - API request/response formats, LangSmith integration details, Terraform variables
- `docs/01-overview.md` - Full feature documentation
- `docs/02-architecture.md` - System diagrams and data flows
- `docs/04-local-development.md` - Development setup guide

## Test Results / Scenario Events (operational notes)

- **Results persistence**: `console-testing-scenarios/logs/scenario_runs/<batchRunId>/events.ndjson` is the source of truth.
- **Common failure mode**: Results UI shows the run but no stages → check `console-testing-scenarios/logs/console_api.log` for `POST /api/scenario-events` returning `401`.
- **Docker env source**: `console-testing-scenarios/docker-compose.yml` loads `../tests/deep_agents/workflow/.env.docker`.
- **Token expectation**: The console API validates `X-Auth-Token` against `CONSOLE_SCENARIO_EVENTS_TOKEN`, else `LANGWATCH_API_KEY`, else `console-local`.

## Architecture Gotchas (lessons learned)

### Environment Variable Precedence

The `tests/deep_agents/workflow/conftest.py` loads `.env` with `override=True`:

```python
load_dotenv(dotenv_path=env_path, override=True)
```

This means `tests/deep_agents/workflow/.env` **takes precedence over Doppler or shell variables**. If you set `LANGWATCH_API_KEY` in Doppler but have a different value in the workflow `.env`, the `.env` value wins.

### Timestamp Format

The Scenario framework sends timestamps in **milliseconds** (e.g., `1770217120681`). The `_parse_ts()` function in `scenario_runs_store.py` must handle this:

```python
if ts > 1e12:  # Likely milliseconds
    ts = ts / 1000
```

### CORS Configuration

When adding new HTTP methods (DELETE, PUT, PATCH), update **both** CORS functions in `console_api.py`:

```python
# In _cors_preflight AND _cors_headers:
headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
```

### LangSmith trace resolution

Use `/api/langsmith-trace` with `thread_id`, `stage_index`, and `num_stages`. **Critical**: `num_stages` must be the **scenario's** stage count (from `inputData.num_stages`), not the batch run total (e.g. not `stagesList.length`). Using the batch total produces the wrong index and `run_id: null`. Runs are taken from the **end** of the sorted list (most recent batch). `thread_id` is reused across sessions; prefer unique-per-session thread ids for clearer mapping. LangSmith `list_runs` limit is 100.

### Input data backfill

When **SCENARIO_INPUT_DATA** events are missing, `scenario_runs_store.py` backfills `input_data` from scenario definitions (keyed by `config.name`). Backfilled data supplies `thread_id`, `num_stages`, and `initial_state` so LangSmith resolution and the UI still work. See `docs/06-test-results.md` for details.

### Trace id vs run id

`trace_ids` on stage are from scenario messages (internal). LangSmith URL uses `run_id` from `/api/langsmith-trace`.

### Persistent cache for run_id

The Test Results UI may cache resolved LangSmith `run_id` by `scenario_run_id` (e.g. in localStorage) so the same stage does not trigger repeated `/api/langsmith-trace` calls.

### React State Updates

For instant UI feedback after mutations (delete, create, update), update local state immediately instead of waiting for API refetch:

```typescript
// Good - instant feedback
setRuns((prev) => prev.filter((r) => r.batch_run_id !== batchRunId));

// Bad - waits for network, feels slow
fetchRuns().catch(() => null);
```

### Key Files for Debugging

| Issue | Check |
|-------|-------|
| 401 on scenario events | `tests/deep_agents/workflow/.env` - is `LANGWATCH_API_KEY` correct? |
| Runs stuck in "running" | `scenario_runs_store.py` `_parse_ts()` - timestamp parsing |
| CORS errors | `console_api.py` `_cors_preflight` and `_cors_headers` |
| UI not updating | Check if local state is updated immediately after API call |
| Missing stages | `logs/scenario_runs/<id>/events.ndjson` - are events persisted? |
| LangSmith trace not resolving / wrong run_id | `TestResults.tsx`: `num_stages` from `inputData.num_stages` not `stagesList.length`; `input_data` has `thread_id`; `console_api.py` `/api/langsmith-trace` logs; `scenario_runs_store.py` backfill if `input_data` missing |