"""Generic node implementations shared by every vertical.

Each function here is a LangGraph node factory: it takes the active
VerticalConfig and returns a plain `(state) -> partial_state` callable. Node
logic stays domain-agnostic; only the prompts/schema passed in via
VerticalConfig change per vertical.
"""
import json
import logging

from app.graph.state import EngineState
from app.graph.vertical import VerticalConfig
from app.llm.retry import invoke_with_retry
from app.llm.router import ModelTier, get_model_with_fallback

logger = logging.getLogger(__name__)


def _parse_json_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            return json.loads(content[start : end + 1])
        raise


def build_extraction_node(config: VerticalConfig):
    def extract(state: EngineState) -> dict:
        model = get_model_with_fallback(ModelTier.LIGHTWEIGHT)
        messages = [
            ("system", config.extraction_prompt),
            ("human", state.get("merged_text", "")),
        ]
        response = invoke_with_retry(model, messages)
        try:
            extracted = _parse_json_response(response.content)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Extraction node: model did not return valid JSON.")
            extracted = {}

        merged = {**state.get("extracted_data", {}), **extracted}
        return {"extracted_data": merged, "status": "in_progress"}

    return extract


def build_gap_check_node(config: VerticalConfig):
    def gap_check(state: EngineState) -> dict:
        extracted = state.get("extracted_data", {})
        missing = [
            field
            for field in config.required_fields
            if not extracted.get(field)
        ]
        return {"missing_fields": missing}

    return gap_check


def build_clarify_node(config: VerticalConfig):
    def clarify(state: EngineState) -> dict:
        missing = state.get("missing_fields", [])
        if not missing:
            return {"follow_up_questions": [], "status": "in_progress"}

        model = get_model_with_fallback(ModelTier.LIGHTWEIGHT)
        prompt = config.clarification_prompt.format(
            missing_fields=", ".join(missing),
            language=state.get("language", "en"),
        )
        response = invoke_with_retry(model, [("system", prompt)])
        questions = [
            line.strip("- ").strip()
            for line in response.content.splitlines()
            if line.strip()
        ]
        return {
            "follow_up_questions": questions,
            "status": "awaiting_clarification",
        }

    return clarify


def build_merge_answers_node(config: VerticalConfig):
    """Folds user answers (collected after a clarification pause) back into
    extracted_data before re-running gap detection / generation."""

    def merge_answers(state: EngineState) -> dict:
        answers = state.get("user_answers", {})
        merged = {**state.get("extracted_data", {}), **answers}
        return {
            "extracted_data": merged,
            "status": "in_progress",
            "follow_up_questions": [],
        }

    return merge_answers


def build_generation_node(config: VerticalConfig):
    def generate(state: EngineState) -> dict:
        model = get_model_with_fallback(ModelTier.PRIMARY)
        structured_model = model.with_structured_output(config.output_schema)

        prompt = config.generation_prompt.format(language=state.get("language", "en"))
        payload = json.dumps(state.get("extracted_data", {}), ensure_ascii=False)

        result = invoke_with_retry(
            structured_model, [("system", prompt), ("human", payload)]
        )
        output = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        return {"structured_output": output}

    return generate


def build_validation_node(config: VerticalConfig):
    def validate(state: EngineState) -> dict:
        output = state.get("structured_output")
        errors: list[str] = []

        if not output:
            errors.append("No structured output was produced.")
        else:
            try:
                model_instance = config.output_schema(**output)
            except Exception as exc:  # pydantic ValidationError or similar
                errors.append(str(exc))
                model_instance = None

            if model_instance and config.extra_validators:
                for validator in config.extra_validators:
                    errors.extend(validator(model_instance))

        if errors:
            return {
                "validation_errors": errors,
                "retry_count": state.get("retry_count", 0) + 1,
            }

        return {"validation_errors": [], "status": "completed"}

    return validate


def route_after_gap_check(state: EngineState) -> str:
    return "clarify" if state.get("missing_fields") else "generate"


def route_after_clarify(state: EngineState) -> str:
    return "pause" if state.get("status") == "awaiting_clarification" else "generate"


def route_after_validate(config: VerticalConfig):
    def _route(state: EngineState) -> str:
        if not state.get("validation_errors"):
            return "done"
        if state.get("retry_count", 0) >= config.max_retries:
            return "failed"
        return "retry"

    return _route
