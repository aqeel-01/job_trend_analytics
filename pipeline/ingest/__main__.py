"""Allow running ingestion via `python -m pipeline.ingest`."""

from pipeline.ingest.cli import main

raise SystemExit(main())
