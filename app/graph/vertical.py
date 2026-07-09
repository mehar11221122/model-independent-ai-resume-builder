"""The plug-in contract every vertical (Resume, Marketing, Automotive, Legal...)
must satisfy to run on the shared engine.

The scope document's core design principle is: "Nothing in the core engine is
domain-specific... each vertical plugs into the same orchestration graph by
supplying its own prompts, extraction schemas, validation rules, and tools."
This dataclass is that plug-in point.
"""
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel


@dataclass
class VerticalConfig:
    name: str
    output_schema: type[BaseModel]
    required_fields: list[str]

    extraction_prompt: str
    generation_prompt: str
    clarification_prompt: str

    # Optional extra business-rule validation beyond schema validation
    # (e.g. duplicate detection, cross-field consistency checks).
    extra_validators: list[Callable[[BaseModel], list[str]]] | None = None

    max_retries: int = 2
