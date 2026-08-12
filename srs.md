


Software Requirements Specification (SRS)
AI-Powered Job Market & Skill Demand Intelligence Pipeline

Document Version: 1.0
Project Versions: V1 — Small/Local | V2 — Scaled/Production-like
Cost Requirement: $0
Primary Domain: Data Engineering + Machine Learning + Agentic AI + MLOps

1. Introduction
1.1 Purpose

The purpose of this project is to build an end-to-end AI-powered job-market intelligence platform that continuously collects publicly available job postings, processes them to extract technical skills and job characteristics, applies machine-learning models to identify emerging skill trends, and uses multiple AI agents to generate actionable reports and alerts.

The system will demonstrate the complete lifecycle of an ML/AI system:

Data → ETL → Storage → Preprocessing → ML → API → Agents → Evaluation → Monitoring → Retraining

Two versions will be implemented:

V1: Small-scale implementation for proving the complete architecture.
V2: Larger and more robust implementation using the same architecture and interfaces.

Both versions must be executable without paying for any API, cloud service, model provider, or proprietary software.

2. Project Objectives

The system shall:

Collect job postings from free public APIs.
Store raw and processed job data.
Clean and normalize job-posting data.
Extract technical skills from job descriptions.
Identify job seniority.
Calculate skill-demand trends.
Train an ML/statistical model.
Deploy the model through a REST API.
Allow AI agents to consume model predictions.
Generate human-readable job-market reports.
Detect unusual changes in skill demand.
Evaluate extraction and prediction quality.
Monitor pipeline health and model behavior.
Retrain the model when new data becomes available.
Compare model versions before and after retraining.
Demonstrate measurable improvement rather than merely demonstrating that the pipeline runs.
3. Non-Goals

The system will not:

provide guaranteed career advice;
make hiring decisions;
automatically apply for jobs;
provide financial/investment advice;
scrape websites in violation of their terms;
depend on paid OpenAI/Anthropic/etc. APIs;
require paid cloud infrastructure;
attempt to train a large language model from scratch;
replace professional labor-market research.
4. Cost Requirements
4.1 Mandatory Requirement

The entire project must be runnable at $0 software/API cost.

Approved components
Component	V1	V2
Job data	Arbeitnow/public API	Arbeitnow + optional free Adzuna
Database	SQLite	PostgreSQL
ML	scikit-learn / SciPy	LightGBM + scikit-learn
API	FastAPI	FastAPI
Agents	LangGraph	LangGraph
LLM	Ollama	Ollama
LLM model	Qwen / Llama / similar local model	Qwen / Llama / similar local model
Monitoring	Python + Prometheus-compatible metrics	Prometheus + Grafana
Containers	Docker	Docker
Scheduling	cron / Python scheduler	cron / GitHub Actions where appropriate
Version control	Git	Git
Experiment tracking	JSON/CSV	MLflow locally
Visualization	Matplotlib/Plotly	Grafana/Plotly

No component is required to have a paid subscription.

5. System Architecture
5.1 V1 Architecture
             ┌──────────────────┐
             │ Arbeitnow API    │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ ETL Pipeline     │
             │ Fetch + Clean    │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ SQLite           │
             │ Raw + Processed  │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Feature Engine   │
             │ Skills/Seniority │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Trend Model      │
             │ Z-score          │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ FastAPI          │
             │ /trending-skills │
             └────────┬─────────┘
                      │
                      ▼
          ┌────────────────────────┐
          │ LangGraph Agent System │
          │                        │
          │ Monitor                │
          │ Analyst                │
          │ Report Writer          │
          └───────────┬────────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Evaluation       │
             │ + Monitoring     │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Retraining       │
             └──────────────────┘
6. V1 Requirements
6.1 V1 Goal

V1 shall demonstrate a complete working pipeline using a relatively small dataset and simple, explainable ML.

The goal is:

Prove that every component works together end-to-end.

6.2 Data Ingestion
Functional Requirements

FR-V1-001: The system shall retrieve job postings from a free public job API.

FR-V1-002: The system shall support Arbeitnow as the primary data source.

FR-V1-003: The ingestion process shall store:

job ID
title
company
location
description
URL
publication date
remote status where available
source
ingestion timestamp

FR-V1-004: The ingestion process shall avoid duplicate job records.

FR-V1-005: The system shall log successful and failed API requests.

FR-V1-006: The ingestion process shall be executable from the command line.

Example:

python -m pipeline.ingest
7. V1 Storage

SQLite shall be used.

Required tables
jobs
skills
job_skills
pipeline_runs
model_runs
agent_runs
jobs
id
source_job_id
title
company
location
description
url
published_at
remote
source
ingested_at
created_at
skills
id
skill_name
category
canonical_name
job_skills
job_id
skill_id
confidence
extraction_method
pipeline_runs
id
started_at
completed_at
status
records_fetched
records_inserted
records_failed
error_message
8. V1 Preprocessing

The preprocessing system shall:

Normalize text.
Remove unnecessary HTML.
Normalize whitespace.
Convert known skill variants to canonical names.
Extract technical skills.
Determine approximate seniority.
Generate weekly aggregation data.
Initial skill taxonomy

Approximately 30–50 skills.

Example:

Python
Java
JavaScript
TypeScript
C++
SQL
PostgreSQL
MySQL
MongoDB
AWS
Azure
GCP
Docker
Kubernetes
Git
Linux
FastAPI
Django
React
Node.js
Angular
TensorFlow
PyTorch
Scikit-learn
Pandas
Spark
Airflow
Kafka
LangChain
LangGraph
Machine Learning
Deep Learning
NLP
LLM
Generative AI

The taxonomy shall be stored as data/configuration rather than hard-coded throughout the application.

9. V1 Skill Extraction

The initial implementation shall use deterministic matching.

For example:

"Experience with Python, Docker and AWS"

→ Python
→ Docker
→ AWS

The system shall support aliases.

Example:

Postgres
PostgreSQL

shall map to:

PostgreSQL
Extraction evaluation

A manually labeled set of approximately 20–50 job descriptions shall be created.

Metrics:

Precision
Recall
F1 score
10. V1 ML Model

V1 shall use a statistical trend model rather than a complex ML model.

For every skill:

current_frequency
previous_frequency
change
z_score

A simplified trend score can be:

z = (current_count - historical_mean) / historical_std

Skills shall then be ranked by trend score.

Output example
{
  "skill": "Kubernetes",
  "current_mentions": 47,
  "previous_mentions": 31,
  "change_percent": 51.6,
  "z_score": 2.14,
  "trend": "rising"
}
11. V1 Model Evaluation

The system shall compare:

Current trend model
Simple frequency baseline

Metrics shall include:

trend ranking stability;
top-k skill overlap;
change detection;
historical validation where sufficient data exists.

The evaluation shall explicitly state the limitations of a small dataset.

12. V1 Model Deployment

FastAPI shall expose the model.

Required endpoint:

GET /trending-skills

Optional:

GET /skills/{skill_name}
GET /health
GET /model-info

Example:

GET /trending-skills?limit=10

Response:

{
  "model_version": "v1.0",
  "generated_at": "...",
  "skills": [
    {
      "skill": "Python",
      "trend_score": 2.1,
      "direction": "up"
    }
  ]
}
13. V1 Agentic System

V1 shall contain three agents.

Agent 1 — Monitor Agent

Responsibilities:

check whether new data exists;
verify pipeline freshness;
detect ingestion failure;
trigger the analysis workflow.

Tools:

database health tool
pipeline status tool
FastAPI health endpoint
Agent 2 — Analyst Agent

Responsibilities:

call the ML API;
retrieve trending skills;
interpret model results;
identify the strongest movements;
distinguish weak signals from strong signals.

The Analyst must consume the ML model output.

This requirement is critical.

The agent must not simply analyze raw job descriptions and pretend the ML model exists.

Agent 3 — Report Writer Agent

Responsibilities:

receive Analyst output;
create a weekly job-market report;
explain why skills are trending;
include evidence from the data;
avoid unsupported claims.

Example report:

Weekly Technology Skill Report

Top Rising Skills
1. Kubernetes
2. LangGraph
3. FastAPI

Kubernetes increased by 51.6% week-over-week.

The strongest growth was observed in remote
backend and ML engineering postings.

Confidence: Medium
14. V1 Agent Workflow
Monitor Agent
      │
      ▼
Data Fresh?
      │
      ▼
Analyst Agent
      │
      ├── calls FastAPI
      │
      └── receives ML predictions
              │
              ▼
       Report Writer Agent
              │
              ▼
        Weekly Report

LangGraph shall manage the state transitions.

15. V1 Evaluation

The system shall evaluate three layers.

Data evaluation
records fetched
records inserted
duplicate rate
failure rate
ML evaluation
skill extraction precision
skill extraction recall
skill extraction F1
trend ranking
Agent evaluation
tool-call success rate
workflow completion rate
invalid output rate
report factuality

A manually reviewed sample shall be used initially.

16. V1 Monitoring

The system shall track:

API failures;
ingestion latency;
number of jobs collected;
duplicate percentage;
preprocessing failures;
model execution time;
agent execution failures;
FastAPI health;
report-generation success.

A simple local dashboard or logs are sufficient for V1.

17. V1 Retraining

Retraining shall occur when new job data is available.

Minimum requirement:

Dataset V1
    ↓
Model V1.0
    ↓
New data
    ↓
Retrain
    ↓
Model V1.1
    ↓
Compare

The system shall record:

model version
training timestamp
training dataset size
model parameters
evaluation metrics
18. V1 Acceptance Criteria

V1 is considered complete when:

 Public data is successfully collected.
 At least several hundred job postings are stored.
 Duplicate jobs are handled.
 Skills are extracted.
 Skill extraction is evaluated.
 Trend scores are generated.
 ML/statistical model is exposed through FastAPI.
 Agents call the API.
 Agents generate a report.
 Pipeline failures are logged.
 Retraining can be executed.
 Two model versions can be compared.
 Entire pipeline runs for $0.