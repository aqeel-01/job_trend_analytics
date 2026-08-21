# Job Market & Skill Demand Intelligence Pipeline

End-to-end AI-powered job market intelligence platform (**V1 — small/local, $0 cost**).

Collects publicly available job postings, extracts technical skills, classifies seniority, computes statistical skill-demand trends, serves results over FastAPI, and uses LangGraph agents (Monitor → Analyst → Report Writer) to produce grounded weekly reports. Local monitoring, model evaluation, and retraining/comparison are included.

**Current status:** V1 complete — ingestion through agents, evaluation, monitoring, and retraining.

## Architecture

```
Arbeitnow API
  → Ingestion (normalize + dedupe)
  → SQLite (jobs, skills, job_skills, pipeline_runs, model_runs, agent_runs)
  → Preprocessing → Skill extraction → Seniority rules
  → Trend model (z-score) → Evaluation
  → FastAPI
  → LangGraph agents (Monitor → Analyst → Report Writer via Ollama)
  → Metrics (JSONL) + Retraining / version comparison
```

## What works today

| Area | Status | Capabilities |
|------|--------|--------------|
| Foundation | Done | Config (`JOB_MARKET_*`), logging, root CLI, SQLite path |
| Ingestion | Done | Arbeitnow fetch, normalize, dedupe, `pipeline_runs` |
| Storage | Done | Schema + repositories for jobs, skills, job_skills, runs |
| Preprocessing | Done | HTML strip, whitespace/text normalization |
| Skill taxonomy | Done | `data/skills_taxonomy.json` (canonical + aliases) |
| Skill extraction | Done | Deterministic matching → `job_skills` |
| Seniority | Done | Rule-based title/description classifier |
| Trend model | Done | Frequency change + historical mean/std + z-score ranking |
| Evaluation | Done | Trend model vs frequency baseline (stability, top-k, change) |
| FastAPI | Done | `/health`, `/model-info`, `/trending-skills`, `/skills/{name}` |
| Monitor Agent | Done | DB health, pipeline freshness, API health, trigger analysis |
| Analyst Agent | Done | Consumes FastAPI ML output; strong/weak signals |
| Report Writer | Done | Ollama LLM + deterministic fallback; markdown reports |
| Orchestrator | Done | Monitor → Analyst → Report; records `agent_runs` |
| Monitoring | Done | Local JSONL metrics + `python -m pipeline metrics` |
| Retraining | Done | Detect new data, version bump, train, compare versions |

## Requirements

- Python 3.11+
- pip
- Optional: [Ollama](https://ollama.com) for LLM report generation (fallback report works without it)

No API keys required for ingestion (Arbeitnow public API).

## Quick start

```bash
git clone <your-repo-url>
cd job-market

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Set Ollama model name to match `ollama list` (example):

```env
JOB_MARKET_OLLAMA_BASE_URL=http://localhost:11434
JOB_MARKET_OLLAMA_MODEL=deepseek-r1:7b
```

## End-to-end workflow

Typical local run:

```bash
# 1. Ingest jobs
python -m pipeline.ingest --max-pages 2

# 2. Extract skills into job_skills
python -m pipeline extract

# 3. Serve the trend API (keep this terminal open)
python -m pipeline.api

# 4a. Full agent pipeline (Monitor → Analyst → Report) when Monitor triggers
python -m pipeline run

# 4b. Or run agents step-by-step
python -m pipeline monitor
python -m pipeline analyst          # writes reports/latest_analyst.json
python -m pipeline report           # uses .env Ollama settings + latest analyst JSON

# 5. Inspect metrics / retrain
python -m pipeline metrics
python -m pipeline retrain
```

Reports are written under `reports/` (e.g. `latest_report.md`, timestamped orchestrator reports).

## CLI reference

### Root commands

```bash
python -m pipeline              # help
python -m pipeline info         # config (DB, Ollama URL/model, report dir)
python -m pipeline extract      # skill extraction over stored jobs
python -m pipeline monitor      # Monitor Agent
python -m pipeline analyst      # Analyst Agent → reports/latest_analyst.json
python -m pipeline report       # Report Writer (default: latest analyst JSON)
python -m pipeline run          # Orchestrator
python -m pipeline metrics      # metrics summary
python -m pipeline retrain      # retrain / compare model versions
```

Flags after a subcommand are forwarded (e.g. `python -m pipeline report --ollama-model deepseek-r1:7b`).

### Module CLIs

```bash
python -m pipeline.ingest --max-pages 2
python -m pipeline.extraction
python -m pipeline.api                    # uvicorn FastAPI (default :8000)
python -m pipeline.agents.monitor
python -m pipeline.agents.analyst
python -m pipeline.agents.report_writer --analyst-report reports/latest_analyst.json
python -m pipeline.agents.orchestrator
python -m pipeline.monitoring --summary
python -m pipeline.retraining train
python -m pipeline.retraining compare --previous v1.0 --current v1.1
```

## FastAPI

Start with `python -m pipeline.api`, then:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/model-info` | Active model metadata |
| GET | `/trending-skills?limit=N` | Ranked skill trends |
| GET | `/skills/{skill_name}` | Detail for one skill |

The Analyst Agent **must** call these endpoints (it does not read raw job descriptions for trends).

## Storage (SQLite)

Default DB: `data/job_market.db`

| Table | Purpose |
|-------|---------|
| `jobs` | Normalized postings (unique on `source`, `source_job_id`) |
| `skills` | Canonical skill catalog |
| `job_skills` | Extraction links (confidence, method) |
| `pipeline_runs` | Ingestion run metadata / freshness |
| `model_runs` | Trained trend model versions + metrics |
| `agent_runs` | Orchestrator / agent execution records |

## Configuration

Settings load from environment variables (prefix `JOB_MARKET_`) and optional `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_MARKET_ENVIRONMENT` | `development` | Runtime environment name |
| `JOB_MARKET_LOG_LEVEL` | `INFO` | Root log level |
| `JOB_MARKET_LOG_FILE` | _(none)_ | Optional log file path |
| `JOB_MARKET_DATABASE_PATH` | `data/job_market.db` | SQLite database path |
| `JOB_MARKET_ARBEITNOW_API_BASE_URL` | Arbeitnow job-board API | Ingestion base URL |
| `JOB_MARKET_INGEST_REQUEST_TIMEOUT_SECONDS` | `30` | HTTP timeout |
| `JOB_MARKET_INGEST_MAX_RETRIES` | `3` | API retry attempts |
| `JOB_MARKET_INGEST_DEFAULT_MAX_PAGES` | _(none)_ | Default page limit |
| `JOB_MARKET_SKILLS_TAXONOMY_PATH` | `data/skills_taxonomy.json` | Skill taxonomy JSON |
| `JOB_MARKET_OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama API |
| `JOB_MARKET_OLLAMA_MODEL` | `llama3` | Model name from `ollama list` |
| `JOB_MARKET_OLLAMA_TIMEOUT_SECONDS` | `120` | Generation timeout |
| `JOB_MARKET_REPORT_OUTPUT_DIR` | `reports` | Markdown / analyst JSON output |
| `JOB_MARKET_METRICS_PATH` | `data/metrics.jsonl` | Local monitoring metrics |

## Project structure

```
pipeline/
  config/           # Pydantic settings
  ingest/           # Arbeitnow client, normalizer, service, CLI
  storage/          # SQLite schema, database, repositories
  preprocess/       # Deterministic JD text cleanup
  skills/           # Taxonomy loader
  extraction/       # Skill matching + persistence CLI
  seniority/        # Rule-based seniority classifier
  trend/            # Weekly series, z-score model, service
  evaluation/       # Trend vs frequency baseline
  api/              # FastAPI app, routes, schemas
  agents/
    monitor/        # Pipeline / DB / API health checks
    analyst/        # FastAPI-backed signal analysis
    report_writer/  # Ollama + fallback markdown reports
    orchestrator/   # End-to-end agent graph
  monitoring/       # JSONL metrics recorder + CLI
  retraining/       # Train, version, compare
  cli.py            # `python -m pipeline`
tests/              # Unit/integration tests per module
data/               # SQLite DB, taxonomy, metrics (mostly gitignored)
reports/            # Generated analyst JSON + markdown reports
docs/               # Documentation stubs
```

## Development

```bash
pytest
pytest -v
```

Tests mock external HTTP (Arbeitnow / FastAPI / Ollama) where needed. Metrics writes are isolated via test fixtures.

Alternative install without editable mode:

```bash
pip install -r requirements.txt
```

### Runtime dependencies

- `httpx` — HTTP client (ingestion, agents, Ollama)
- `pydantic` / `pydantic-settings` — config and validation
- `fastapi` / `uvicorn` — model serving
- `langgraph` — agent workflows

## V1 checklist

- [x] Project foundation
- [x] Data ingestion (Arbeitnow → SQLite)
- [x] Preprocessing & skill taxonomy
- [x] Deterministic skill extraction
- [x] Seniority classification
- [x] Trend model & evaluation
- [x] FastAPI serving
- [x] LangGraph agents (Monitor, Analyst, Report Writer)
- [x] Orchestrator + agent run recording
- [x] Local monitoring metrics
- [x] Retraining & model version comparison

## License

TBD
