# Job Market & Skill Demand Intelligence Pipeline

End-to-end AI-powered job market intelligence platform (**V1 — small/local, $0 cost**).

Collects publicly available job postings, extracts technical skills, applies statistical trend models, and uses AI agents to generate actionable reports. See [srs.md](srs.md) (full SRS) and [docs/SRS.md](docs/SRS.md) for requirements.

**Current status:** Phase 1 complete — project foundation + Arbeitnow job ingestion into SQLite.

## What works today

| Phase | Status | Capabilities |
|-------|--------|--------------|
| Phase 0 | Done | Config, logging, CLI skeleton, SQLite path configuration |
| Phase 1 | Done | Arbeitnow API fetch, normalization, deduplicated SQLite storage, `python -m pipeline.ingest` |
| Phase 2+ | Planned | Preprocessing, skill extraction, ML, FastAPI, agents, monitoring, retraining |

## Architecture (V1 target)

```
Arbeitnow API → ETL / Ingestion → SQLite → Feature Engine → Trend Model → FastAPI → LangGraph Agents
                     ▲
              implemented here
```

## Requirements

- Python 3.11+
- pip

No API keys required for ingestion (Arbeitnow public API).

## Quick start

```bash
# Clone and enter the repo
git clone <your-repo-url>
cd job-market

# Virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install package + dev tools (pytest)
pip install -e ".[dev]"
```

Copy the environment template:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

## Usage

### Main CLI

```bash
python -m pipeline              # help
python -m pipeline info         # show resolved configuration
```

### Job ingestion (Arbeitnow)

```bash
python -m pipeline.ingest                    # fetch all available pages
python -m pipeline.ingest --max-pages 2      # limit pages (useful for dev)
python -m pipeline.ingest --log-level DEBUG
```

Ingestion stores normalized jobs in SQLite (`data/job_market.db` by default) and records run metadata in `pipeline_runs`. Duplicate jobs are skipped via a unique constraint on `(source, source_job_id)`.

### Stored job fields

Each ingested job includes:

- `source_job_id`, title, company, location, description, URL
- publication date (`published_at`)
- remote status (when available)
- source (`arbeitnow`)
- ingestion timestamp (`ingested_at`)

## Configuration

Settings load from environment variables (prefix `JOB_MARKET_`) and an optional `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_MARKET_ENVIRONMENT` | `development` | Runtime environment name |
| `JOB_MARKET_LOG_LEVEL` | `INFO` | Root log level |
| `JOB_MARKET_LOG_FILE` | _(none)_ | Optional log file path |
| `JOB_MARKET_DATABASE_PATH` | `data/job_market.db` | SQLite database path |
| `JOB_MARKET_ARBEITNOW_API_BASE_URL` | `https://www.arbeitnow.com/api/job-board-api` | Arbeitnow API base URL |
| `JOB_MARKET_INGEST_REQUEST_TIMEOUT_SECONDS` | `30` | HTTP timeout for ingestion |
| `JOB_MARKET_INGEST_MAX_RETRIES` | `3` | API retry attempts |
| `JOB_MARKET_INGEST_DEFAULT_MAX_PAGES` | _(none)_ | Default page limit per run |

## Project structure

```
pipeline/                 # Main application package
  config/                 # Pydantic settings
  ingest/                 # Phase 1: API client, normalizer, storage, service, CLI
    client.py             # Arbeitnow HTTP client (retries + logging)
    normalizer.py         # API → internal JobPosting model
    storage.py            # SQLite jobs + pipeline_runs tables
    service.py            # Ingestion orchestration
    cli.py                # `python -m pipeline.ingest`
  cli.py                  # Root CLI (`python -m pipeline`)
tests/
  ingest/                 # Ingestion unit tests (mocked API)
  fixtures/               # Sample Arbeitnow API responses
data/                     # Local SQLite DB (gitignored; .gitkeep tracked)
docs/                     # Documentation
srs.md                    # Full software requirements specification
```

## Development

Run the test suite (no live API calls — tests use mocked responses):

```bash
pytest
pytest -v
```

Install from `requirements.txt` if you prefer not to use editable install:

```bash
pip install -r requirements.txt
```

### Dependencies (runtime)

- `httpx` — HTTP client for Arbeitnow API
- `pydantic` / `pydantic-settings` — configuration and validation

## Roadmap (V1)

- [x] Phase 0: Project foundation
- [x] Phase 1: Data ingestion (Arbeitnow API → SQLite)
- [ ] Phase 2: Preprocessing & text normalization
- [ ] Phase 3: Skill extraction & evaluation
- [ ] Phase 4: Trend model & FastAPI
- [ ] Phase 5: LangGraph agents (Monitor, Analyst, Report Writer)
- [ ] Phase 6: Monitoring, evaluation, retraining

## License

TBD
