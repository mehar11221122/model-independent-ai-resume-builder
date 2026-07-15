from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes import health, resume
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Model-Independent AI Engine",
    description=(
        "Reusable, model-independent AI Engine (LangGraph + LangChain + "
        "OpenRouter) with the Resume Builder as its first vertical module."
    ),
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(resume.router)


@app.get("/")
def root() -> FileResponse:
    """Lightweight demo UI for exercising the Resume Builder without needing
    to hand-craft API calls. This is a QA/demo aid, not the client-facing
    front-end app referenced in the scope document (that remains out of
    scope for this backend-only milestone).

    Cache-Control is disabled: this page is still actively being iterated
    on, and a stale cached copy in the browser silently running old
    JavaScript against the current API is a worse experience than always
    re-fetching a small HTML file."""
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api")
def api_info() -> dict[str, str]:
    return {
        "name": "Model-Independent AI Engine",
        "docs": "/docs",
        "env": settings.app_env,
    }
