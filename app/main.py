from fastapi import FastAPI

from app.api.routes import health, resume
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

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
def root() -> dict[str, str]:
    return {
        "name": "Model-Independent AI Engine",
        "docs": "/docs",
        "env": settings.app_env,
    }
