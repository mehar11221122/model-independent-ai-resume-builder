"""Maps a vertical name to its compiled workflow graph.

Adding a new vertical to the running app is: write a VerticalConfig, register
it here. No engine code changes.
"""
from functools import lru_cache

from app.graph.vertical import VerticalConfig
from app.graph.workflow import build_workflow
from app.modules.resume.config import RESUME_VERTICAL

VERTICALS: dict[str, VerticalConfig] = {
    "resume": RESUME_VERTICAL,
}


@lru_cache
def get_workflow(vertical: str):
    if vertical not in VERTICALS:
        raise ValueError(f"Unknown vertical: {vertical}")
    return build_workflow(VERTICALS[vertical])
