"""FastAPI application factory for the V1 model-serving layer."""

from fastapi import FastAPI

from pipeline import __version__
from pipeline.api.routes import router


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Job Market Intelligence API",
        description=(
            "V1 skill-demand trend model API. "
            "Exposes the statistical z-score trend model results."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.include_router(router)
    return app


app = create_app()
