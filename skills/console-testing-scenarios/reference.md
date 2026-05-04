# Console Testing Scenarios - Reference

## API Request/Response Formats

### POST /run-scenario

**Batch format (preferred)**:
```json
{
  "batch_run_id": "optional-string",
  "dataset_id": "uuid",
  "max_concurrency": 4,
  "num_repetitions": 1,
  "experiment_prefix": "eval",
  "runs": [
    {"scenario": "scenario_name", "example_id": "example-uuid"}
  ]
}
```

**Legacy single format**:
```json
{
  "dataset_id": "uuid",
  "scenario": "scenario_name",
  "example_id": "example-uuid",
  "max_concurrency": 4,
  "num_repetitions": 1,
  "experiment_prefix": "eval"
}
```

**Response** (HTTP 200 for executed runs, even if scenarios fail):
```json
{
  "status": "ok|failed",
  "success": true|false,
  "batch_run_id": "console-...",
  "run_status": "finished|error",
  "runs": [
    {
      "scenario": "scenario_name",
      "example_id": "example-uuid",
      "success": true,
      "experiment_name": "eval-scenario_name-20250124-120000"
    }
  ]
}
```

**HTTP semantics**:
- `200`: run executed (may still have failing scenarios; `success=false`)
- `400`: validation error
- `500`: unexpected exception prevented completion (`run_status="error"`)

### GET /datasets-with-examples

**Response**:
```json
{
  "status": "ok",
  "datasets": [
    {
      "id": "uuid",
      "name": "dataset-name",
      "description": "...",
      "created_at": "2025-01-01T00:00:00Z",
      "example_count": 5,
      "examples": ["ex1", "ex2"],
      "examples_metadata": [
        {"id": "ex1", "metadata": {"judge": "scenario_name"}}
      ]
    }
  ]
}
```

### GET /reasonings/ratings

**Response**:
```json
{
  "status": "ok",
  "rows": [
    {
      "id": "uuid",
      "external_id": "...",
      "load_id": "...",
      "load_task_id": "...",
      "statement": "Agent reasoning text...",
      "created_at": "2025-01-01T00:00:00Z",
      "is_positive": true,
      "description": "User feedback comment",
      "feedback_date": "2025-01-02T00:00:00Z"
    }
  ]
}
```

### GET /sse/log-tail

**Response**: `text/event-stream`

**Events**:
- `event: log` - Log content chunk
- `event: error` - Error message

---

## Scenario Events (Test Results)

Scenario can publish LangWatch-style events to the console API:

- Ingestion: `POST /api/scenario-events`
- Live stream: `GET /sse/scenario-events?batch_run_id=<id>`
- Reads: `GET /scenario-runs`, `GET /scenario-runs/<id>/stages`, `GET /scenario-runs/<id>/stages/<scenarioRunId>`
- Delete: `DELETE /scenario-runs/<id>` (returns 400 if run is active, 404 if not found)

### Auth token

Scenario posts with header `X-Auth-Token`.

The console API expects a token using this precedence:

1. `CONSOLE_SCENARIO_EVENTS_TOKEN`
2. else `LANGWATCH_API_KEY`
3. else `"console-local"`

**Symptom**: Results shows the run but stages are empty → check `console-testing-scenarios/logs/console_api.log` for `POST /api/scenario-events` returning `401`.

## LangSmith (Test Results)

### GET /api/langsmith-config

No query params. Response: `{"status": "ok", "org_id": "<LANGSMITH_ORG_ID>", "project_id": "<LANGSMITH_PROJECT_ID>"}`. Used to build `https://smith.langchain.com/o/{org_id}/projects/p/{project_id}?peek={run_id}&peeked_trace={run_id}`.

### GET /api/langsmith-trace

**Query params**: `thread_id` (required), `stage_index` (default 0), `num_stages` (default 2).

**Response**: `{"status": "ok", "run_id": "uuid"}` or `{"status": "ok", "run_id": null}`.

**Behavior**: Resolution uses the last `num_stages` runs for `thread_id`; index = `len(runs) - num_stages + stage_index`. LangSmith project from `LANGCHAIN_PROJECT` or `LANGSMITH_PROJECT`, else `"scenario-framework"`. `list_runs(..., limit=100)` (API maximum 100).

## LangSmith Integration

**Env vars for trace deep links**: `LANGSMITH_ORG_ID`, `LANGSMITH_PROJECT_ID` (optional). For **run listing** (trace resolution): `LANGCHAIN_PROJECT` or `LANGSMITH_PROJECT`.

**thread_id**: Comes from scenario config (`ScenarioConfig.thread_id`). Reused across runs; for more reliable stage→trace mapping, use a thread_id unique per test session when possible.

**SCENARIO_INPUT_DATA**: Custom event type; requires `scenarioId` and `inputData`. Ingested like other events; used to attach `input_data` (and thus `thread_id`/`stage_index`) to stages. Stage details include `input_data` and `trace_ids`; only `run_id` from `/api/langsmith-trace` should be used for the LangSmith URL.

### Dataset Example Required Metadata

Each example must include metadata for the web app to execute correctly:

| Field | Required | Description |
|-------|----------|-------------|
| `judge` | **Yes** | Scenario name from `SCENARIO_BUILDERS` |
| `now` | Recommended | ISO timestamp for time-sensitive scenarios |
| `task_instruction_type` | Recommended | Workflow type |
| `thread_id` | Optional | Original trace thread ID |

**Example metadata**:
```json
{
  "judge": "inbound_eta_validation_valid_sms",
  "now": "2025-11-13T10:00:00Z",
  "task_instruction_type": "pickup_eta_checkpoint"
}
```

### Judge-Scenario Mapping

The `judge` field maps to `ALL_SCENARIO_BUILDERS`:
- `confirm_delivery` workflows: 68 scenarios
- `pickup_eta_checkpoint` workflows: 28 scenarios
- Total: 96 scenarios

### Adding Examples with Judge Metadata

```bash
.venv/bin/python tests/deep_agents/workflow/scripts/create_regression_datasets.py \
    add-standard <run_id> --judge inbound_eta_validation_valid_sms

# List all available judges
.venv/bin/python tests/deep_agents/workflow/scripts/create_regression_datasets.py list-judges
```

---

## Aurora Database Schema

### Tables

**reasonings**:
| Column | Type |
|--------|------|
| id | UUID |
| external_id | VARCHAR |
| load_id | VARCHAR |
| load_task_id | VARCHAR |
| statement | TEXT |
| created_at | TIMESTAMP |

**reasoning_ratings**:
| Column | Type |
|--------|------|
| reasoning_id | UUID (FK) |
| is_positive | BOOLEAN |
| description | TEXT |
| created_at | TIMESTAMP |

### Join Query (used by API)

```sql
SELECT r.id, r.external_id, r.load_id, r.load_task_id, r.statement, r.created_at,
       rr.is_positive, rr.description, rr.created_at AS feedback_date
FROM reasonings r
INNER JOIN reasoning_ratings rr ON r.id = rr.reasoning_id;
```

---

## Terraform Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `region` | string | `us-east-1` | AWS region |
| `vpc_id` | string | (required) | VPC to deploy into |
| `create_subnet` | bool | `true` | Create new public subnet |
| `subnet_cidr` | string | `10.0.101.0/24` | New subnet CIDR |
| `subnet_az` | string | `us-east-1a` | Availability zone |
| `public_subnet_id` | string | `""` | Existing subnet (if not creating) |
| `ssh_cidr` | string | `0.0.0.0/0` | Allowed SSH CIDR |
| `instance_type` | string | `t3.small` | EC2 instance type |
| `key_pair_name` | string | `console-watchtower-key` | SSH key pair name |
| `ecr_repo` | string | `850995563170.dkr.ecr...` | ECR repository URI |
| `api_image_tag` | string | `console-api-latest` | API Docker image tag |
| `frontend_image_tag` | string | `console-frontend-latest` | Frontend image tag |

### Terraform Outputs

| Output | Description |
|--------|-------------|
| `instance_public_ip` | Public IP of EC2 instance |
| `instance_public_dns` | Public DNS of EC2 instance |
| `security_group_id` | Security group ID |
| `subnet_id` | Subnet used for instance |
| `generated_private_key_pem` | SSH private key (if generated) |

---

## Frontend TypeScript Types

### DatasetWithExamples

```typescript
type DatasetWithExamples = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  example_count: number;
  examples: string[];
  examples_metadata?: {
    id: string;
    metadata?: {
      judge?: string;
      [key: string]: unknown;
    };
  }[];
};
```

### ReasoningRating

```typescript
type ReasoningRating = {
  id: string;
  statement: string;
  description: string;
  is_positive: boolean | number | string | null;
  created_at?: string;
  feedback_date?: string;
  external_id?: string;
  load_id?: string;
  load_task_id?: string;
};
```

---

## Docker Compose Services

### console-api
- Build context: Project root (`..`)
- Dockerfile: `console-testing-scenarios/Dockerfile`
- Port: `5001:5001`
- Env file: `tests/deep_agents/workflow/.env.docker`
- Volumes:
  - `./logs:/app/console-testing-scenarios/logs`
  - `~/.aws:/root/.aws:ro`

### console-frontend
- Build context: `./freight-hero-console`
- Dockerfile: `freight-hero-console/Dockerfile`
- Port: `5173:5173`
- Build arg: `VITE_API_BASE`
- Depends on: `console-api`

---

## Deployment Commands

### Push to ECR

```bash
cd console-testing-scenarios
./push_ecr.sh [tag]  # default: latest
```

### Apply Terraform

```bash
cd console-testing-scenarios/infra
terraform init
terraform plan -var="vpc_id=vpc-0e035773bde3d9d85"
terraform apply -var="vpc_id=vpc-0e035773bde3d9d85"
```

### SSH to Instance

```bash
ssh -i infra/console-watchtower-key.pem ec2-user@<instance_public_ip>
```

---

## Error Response Format

All API endpoints return errors consistently:

```json
{
  "status": "error",
  "message": "Error description"
}
```

**HTTP Status Codes**:
- `200` - Success
- `400` - Bad request (validation errors)
- `404` - Not found
- `500` - Server error
