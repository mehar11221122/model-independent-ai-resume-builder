"""Generic node implementations shared by every vertical.

Each function here is a LangGraph node factory: it takes the active
VerticalConfig and returns a plain `(state) -> partial_state` callable. Node
logic stays domain-agnostic; only the prompts/schema passed in via
VerticalConfig change per vertical.
"""
import json
import logging
from typing import Any

from app.core.config import get_settings
from app.graph.state import EngineState
from app.graph.vertical import VerticalConfig
from app.llm import cache as llm_cache
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
        settings = get_settings()
        merged_text = state.get("merged_text", "")
        # Exact-match cache: identical source text (a retried/duplicate
        # submission, or repeat demo/test input) skips the model entirely.
        # Cache key includes the prompt text itself so an edited prompt in
        # a future deploy can never serve a stale result computed under
        # old instructions.
        cache_key = llm_cache.make_key("extract", config.name, config.extraction_prompt, merged_text)
        extracted = llm_cache.get(cache_key) if settings.llm_cache_enabled else None

        if extracted is None:
            model = get_model_with_fallback(
                ModelTier.LIGHTWEIGHT, max_tokens=settings.max_tokens_extract
            )
            messages = [
                ("system", config.extraction_prompt),
                ("human", merged_text),
            ]
            response = invoke_with_retry(model, messages)
            try:
                extracted = _parse_json_response(response.content)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Extraction node: model did not return valid JSON.")
                extracted = {}
            # Never cache an empty/failed result - a free-tier model can be
            # flaky, and a future retry of the identical input deserves a
            # fresh attempt rather than being locked into today's failure.
            if extracted and settings.llm_cache_enabled:
                llm_cache.put(
                    cache_key, extracted,
                    ttl_seconds=settings.llm_cache_ttl_seconds,
                    max_entries=settings.llm_cache_max_entries,
                )

        merged = {**state.get("extracted_data", {}), **extracted}
        return {"extracted_data": merged, "status": "in_progress"}

    return extract


_CONFLICT_PREFIX = "conflict::"

# Virtual field for the "should I generate now, or is there more?" pause -
# see `VerticalConfig.confirm_before_generate`. Deliberately vertical-agnostic
# (no mention of "resume" etc.) since this lives in the generic engine core.
_CONFIRM_FIELD = "final_confirmation"
_CONFIRM_QUESTIONS = {
    "en": "I think I have everything I need! Should I go ahead and generate it now, or is there more information you'd like to add first?",
    "ar": "أعتقد أنني حصلت على كل ما أحتاجه! هل أبدأ الآن، أم توجد معلومات إضافية تريد إضافتها أولاً؟",
}
_CONFIRM_OPTIONS = {
    "en": ["Yes, generate it now", "Wait, I have more to add"],
    "ar": ["نعم، ابدأ الآن", "انتظر، لدي معلومات إضافية"],
}
_CONFIRM_YES_SIGNALS = {
    "yes", "yes please", "yeah", "yep", "sure", "go ahead", "y",
    "yes, generate it now", "yes generate it now", "generate it now",
    "نعم", "نعم، ابدأ الآن", "نعم ابدأ الآن", "ابدأ", "ابدأ الآن", "تفضل",
}


def _is_confirmation_yes(answer: str) -> bool:
    normalized = (answer or "").strip().strip(".!؟?").lower()
    return normalized in _CONFIRM_YES_SIGNALS


def _public_extracted_data(extracted: dict) -> dict:
    """Strip engine-internal control keys (leading underscore) before an
    extracted-data blob is serialized into an LLM prompt payload, so they
    never show up as confusing noise next to real candidate data."""
    return {k: v for k, v in extracted.items() if not k.startswith("_")}


def _detect_conflicts(extracted: dict) -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    """Generic (vertical-agnostic) handling of the `extracted_data["conflicts"]`
    convention: any extraction prompt can flag that two input sources
    disagreed about the same fact by adding
    `{"field": <key>, "values": [...], "note": <optional>}` entries there.
    This turns each unresolved one into a virtual "conflict::<field>"
    missing field with a hint describing exactly what's contradictory, so
    the normal clarify loop asks the user to pick the right value - the
    engine core has zero domain knowledge of what the conflicting field
    means, it just surfaces it.
    """
    extra_missing: list[str] = []
    hints: dict[str, str] = {}
    options: dict[str, list[str]] = {}
    for conflict in extracted.get("conflicts") or []:
        field = conflict.get("field") if isinstance(conflict, dict) else None
        if not field:
            continue
        virtual_field = f"{_CONFLICT_PREFIX}{field}"
        extra_missing.append(virtual_field)
        values = conflict.get("values") or []
        note = conflict.get("note") or ""
        hints[virtual_field] = (
            f"the sources disagree on '{field}' - values found: "
            + ", ".join(str(v) for v in values)
            + (f" ({note})" if note else "")
            + " - ask the user which one is correct"
        )
        if values:
            options[virtual_field] = [str(v) for v in values]
    return extra_missing, hints, options


def merge_user_answers(extracted_data: dict, answers: dict, language: str = "en") -> dict:
    """Fold clarification answers back into extracted_data. Shared by the
    `merge_answers` node and `resume_with_answers` (which must replicate the
    node's effect itself, since LangGraph's `as_node` resume trick skips
    actually running it) so the two can't drift out of sync.

    Answers keyed "conflict::<field>" resolve a detected conflict: the
    answer overwrites the real field and the matching entry is dropped from
    extracted_data["conflicts"] so it isn't asked about again.

    The `final_confirmation` answer (see `_CONFIRM_FIELD`) is handled
    specially rather than stored as a literal field: an affirmative answer
    sets the internal `_ready_to_generate` flag gap_check checks before
    re-asking, while anything else (the "I have more to add" option, or any
    free text the user actually typed) is folded into a running
    `additional_context` note instead - so declining to confirm never loses
    whatever the user just said.

    Everything else is a plain flat merge.
    """
    merged = dict(extracted_data)
    resolved_fields = []
    for key, value in answers.items():
        if key == _CONFIRM_FIELD:
            if _is_confirmation_yes(str(value)):
                merged["_ready_to_generate"] = True
            else:
                merged["_ready_to_generate"] = False
                extra_text = str(value).strip()
                is_just_the_more_button = extra_text in _CONFIRM_OPTIONS.get(language, []) or extra_text in _CONFIRM_OPTIONS["en"]
                if extra_text and not is_just_the_more_button:
                    existing = merged.get("additional_context", "")
                    merged["additional_context"] = (existing + "\n" + extra_text).strip()
        elif key.startswith(_CONFLICT_PREFIX):
            real_field = key[len(_CONFLICT_PREFIX):]
            merged[real_field] = value
            resolved_fields.append(real_field)
        else:
            merged[key] = value

    if resolved_fields and merged.get("conflicts"):
        merged["conflicts"] = [
            c for c in merged["conflicts"]
            if not (isinstance(c, dict) and c.get("field") in resolved_fields)
        ]
    return merged


def build_gap_check_node(config: VerticalConfig):
    def gap_check(state: EngineState) -> dict:
        extracted = state.get("extracted_data", {})
        missing = [
            field
            for field in config.required_fields
            if not extracted.get(field)
        ]
        if config.extra_missing_check:
            for field in config.extra_missing_check(extracted):
                if field not in missing:
                    missing.append(field)

        conflict_fields, conflict_hints, conflict_options = _detect_conflicts(extracted)
        for field in conflict_fields:
            if field not in missing:
                missing.append(field)

        # Answers the answer-check node just rejected must be asked again
        # (with its specific reason as the hint) even if the now-reverted
        # field wouldn't otherwise show up as missing under the checks
        # above - e.g. a virtual completeness field that only exists while
        # unanswered.
        hints = dict(conflict_hints)
        prior_hints = state.get("missing_field_hints") or {}
        for field in state.get("invalid_answer_fields") or []:
            if field not in missing:
                missing.append(field)
            hints.setdefault(field, prior_hints.get(field, ""))

        options = dict(conflict_options)
        if not missing and config.confirm_before_generate and not extracted.get("_ready_to_generate"):
            missing.append(_CONFIRM_FIELD)
            options[_CONFIRM_FIELD] = _CONFIRM_OPTIONS.get(
                state.get("language", "en"), _CONFIRM_OPTIONS["en"]
            )

        return {
            "missing_fields": missing,
            "missing_field_hints": hints,
            "missing_field_options": options,
            "invalid_answer_fields": [],
        }

    return gap_check


_EMPTY_ANSWER_REASON = {
    "en": "That came through empty - could you give me an answer?",
    "ar": "بدت الإجابة فارغة - هل يمكنك تزويدي بإجابة؟",
}
_ECHOED_QUESTION_REASON = {
    "en": "That looks like the question itself, not an answer - could you tell me the actual answer?",
    "ar": "يبدو أن هذا هو نص السؤال نفسه وليس إجابة - هل يمكنك إعطائي الإجابة الفعلية؟",
}


def _normalize_for_compare(text: str) -> str:
    return (text or "").strip().rstrip("?!.\u061f").lower()


def build_answer_check_node(config: VerticalConfig):
    """Sanity-checks the answers a user just gave against the specific
    question that prompted them, before they're trusted for generation.

    Without this, `merge_user_answers` folds free-text answers into
    `extracted_data` blindly - so a user pasting career achievements when
    asked about education, or answering an education question with only
    dates and no degree/subject, would silently pass through unnoticed.

    A cheap, vertical-agnostic heuristic pass runs first and catches the
    answers with an unambiguous verdict - empty/whitespace, or the user
    accidentally pasting the question text itself back - with zero LLM
    calls. Only the remaining, genuinely ambiguous answers (does this
    actually address what was asked?) get sent to a cheap LLM call, which
    judges purely from the question/answer text so it works the same for
    any vertical. If the heuristic pass already caught every answer in the
    batch, the model is never called at all. Rejected answers (from either
    path) are reverted out of `extracted_data` and routed back to
    `missing_fields` (via `invalid_answer_fields`, which `gap_check` folds
    in) with a specific hint about what was still needed.
    """

    def check_answers(state: EngineState) -> dict:
        answers = state.get("user_answers") or {}
        questions = {q["field"]: q["question"] for q in state.get("follow_up_questions") or []}
        pairs = {
            field: {"question": questions[field], "answer": value}
            for field, value in answers.items()
            if field in questions
            and not field.startswith(_CONFLICT_PREFIX)
            and field != _CONFIRM_FIELD
        }
        if not pairs:
            return {"follow_up_questions": []}

        language = state.get("language", "en")

        invalid_map: dict[str, str] = {}
        remaining_pairs: dict[str, dict[str, str]] = {}
        for field, pair in pairs.items():
            answer = pair["answer"]
            if not (answer or "").strip():
                invalid_map[field] = _EMPTY_ANSWER_REASON.get(language, _EMPTY_ANSWER_REASON["en"])
            elif _normalize_for_compare(answer) == _normalize_for_compare(pair["question"]):
                invalid_map[field] = _ECHOED_QUESTION_REASON.get(language, _ECHOED_QUESTION_REASON["en"])
            else:
                remaining_pairs[field] = pair

        if remaining_pairs:
            settings = get_settings()
            # The instructions are fixed text, identical on every single call
            # regardless of language or field content - kept in their own
            # "system" message (rather than interpolated into one big string
            # together with the per-call `remaining_pairs` payload below) so
            # a provider's prompt/prefix caching can actually recognize and
            # discount this repeated block instead of seeing a "new" prompt
            # every time just because the payload appended to it changed.
            instructions = (
                "You are a strict answer-quality checker for a form-filling "
                "assistant. For each field below you're given the exact "
                "question that was asked and the user's raw answer. Judge "
                "whether the answer genuinely and sufficiently addresses THAT "
                "question.\n\n"
                "Mark an answer invalid (valid=false) when it: talks about a "
                "clearly different topic than what was asked (e.g. describing "
                "work achievements when asked about education); is empty, a "
                "placeholder, or a refusal with no real information; or is "
                "on-topic but missing a specific detail the question itself "
                "asked for (e.g. only giving dates for an education question "
                "that also asked for the degree/subject and school name).\n\n"
                "Do not mark an answer invalid just because it's brief, "
                "informal, or honestly says something doesn't apply (e.g. "
                "\"none\") - that is a valid answer.\n\n"
                "Output ONLY a JSON object keyed by field name, each value "
                '{"valid": bool, "reason": str}. When valid is false, `reason` '
                "must be a short, specific follow-up question asking for "
                "exactly the missing/corrected detail, written in the same "
                "language as the fields below. No commentary, no markdown "
                "fences."
            )
            payload = f"Fields:\n{json.dumps(remaining_pairs, ensure_ascii=False, sort_keys=True)}\n\nLanguage: {language}"

            cache_key = llm_cache.make_key("check_answers", config.name, instructions, payload)
            cached_verdicts = llm_cache.get(cache_key) if settings.llm_cache_enabled else None

            if cached_verdicts is not None:
                verdicts = cached_verdicts
            else:
                model = get_model_with_fallback(
                    ModelTier.LIGHTWEIGHT, max_tokens=settings.max_tokens_check_answers
                )
                try:
                    response = invoke_with_retry(
                        model,
                        [
                            ("system", instructions),
                            ("human", payload),
                        ],
                    )
                    verdicts = _parse_json_response(response.content)
                    if isinstance(verdicts, dict) and settings.llm_cache_enabled:
                        llm_cache.put(
                            cache_key, verdicts,
                            ttl_seconds=settings.llm_cache_ttl_seconds,
                            max_entries=settings.llm_cache_max_entries,
                        )
                except Exception as exc:  # noqa: BLE001
                    # Fail open: an unreliable free-tier checker call should
                    # never permanently block a user from finishing their
                    # resume - and a failure is never cached either, so a
                    # retry of the same input gets a fresh attempt. The
                    # heuristic-caught fields above still get applied either
                    # way.
                    logger.warning(
                        "Answer-check node: verdict call failed, accepting answers as-is: %s", exc
                    )
                    verdicts = {}

            if isinstance(verdicts, dict):
                for field in remaining_pairs:
                    verdict = verdicts.get(field)
                    if isinstance(verdict, dict) and verdict.get("valid") is False:
                        invalid_map[field] = str(
                            verdict.get("reason")
                            or "That answer didn't seem to address this - could you try again?"
                        )

        if not invalid_map:
            return {"follow_up_questions": []}

        extracted = dict(state.get("extracted_data", {}))
        hints = dict(state.get("missing_field_hints") or {})
        for field, reason in invalid_map.items():
            extracted.pop(field, None)
            hints[field] = reason

        return {
            "extracted_data": extracted,
            "invalid_answer_fields": list(invalid_map),
            "missing_field_hints": hints,
            "follow_up_questions": [],
        }

    return check_answers


def _templated_question(
    field: str,
    config: VerticalConfig,
    hints: dict[str, str],
    options: list[str] | None,
    language: str,
) -> str:
    """Deterministically phrases a question for a missing field - no LLM.

    Every field a vertical's own schema/completeness checks can produce is
    known ahead of time, so `config.field_questions` covers it with a
    hand-written, per-language question in the common case. The remaining
    two cases are handled generically, still without a model:
    - `conflict::<field>` fields (see `_detect_conflicts`) get a question
      built directly from the conflicting values already computed into
      `options` - there's nothing to "generate", the values ARE the
      question.
    - Anything else (a vertical that hasn't written a template for some
      field) gets a generic, still-legible fallback built from `hints`.
    """
    templates = (config.field_questions or {}).get(field)
    if templates:
        return templates.get(language) or templates.get("en") or next(iter(templates.values()))

    if field.startswith(_CONFLICT_PREFIX):
        real_field = field[len(_CONFLICT_PREFIX):]
        names = (config.conflict_field_labels or {}).get(real_field, {})
        label = names.get(language) or names.get("en") or real_field.replace("_", " ")
        values = ", ".join(options or [])
        if language == "ar":
            return f"لاحظت معلومات مختلفة بخصوص {label}: {values}. أي منها هو الصحيح؟"
        return f"I found different information for {label}: {values}. Which one is correct?"

    hint = hints.get(field)
    label = field.replace("_", " ")
    if language == "ar":
        return f"هل يمكنك إخباري بمزيد من المعلومات حول \"{label}\"؟" + (f" ({hint})" if hint else "")
    return f"Could you tell me about {hint or label}?"


def build_clarify_node(config: VerticalConfig):
    def clarify(state: EngineState) -> dict:
        missing = state.get("missing_fields", [])
        if not missing:
            return {"follow_up_questions": [], "status": "in_progress"}

        options_by_field = state.get("missing_field_options") or {}
        language = state.get("language", "en")
        hints = {**(config.field_hints or {}), **(state.get("missing_field_hints") or {})}

        questions: list[dict[str, Any]] = []
        for field in missing:
            if field == _CONFIRM_FIELD:
                question_text = _CONFIRM_QUESTIONS.get(language, _CONFIRM_QUESTIONS["en"])
            else:
                question_text = _templated_question(
                    field, config, hints, options_by_field.get(field), language
                )
            entry: dict[str, Any] = {"field": field, "question": question_text}
            opts = options_by_field.get(field)
            if opts:
                entry["options"] = opts
            questions.append(entry)

        return {
            "follow_up_questions": questions,
            "status": "awaiting_clarification",
        }

    return clarify


def build_merge_answers_node(config: VerticalConfig):
    """Folds user answers (collected after a clarification pause) back into
    extracted_data before re-running gap detection / generation.

    Deliberately leaves `follow_up_questions` untouched (rather than
    clearing it) - the very next node, `check_answers`, needs the original
    question text to judge whether each answer actually addressed it, and
    clears the list itself once it's done with it.
    """

    def merge_answers(state: EngineState) -> dict:
        merged = merge_user_answers(
            state.get("extracted_data", {}),
            state.get("user_answers", {}),
            state.get("language", "en"),
        )
        return {
            "extracted_data": merged,
            "status": "in_progress",
        }

    return merge_answers


def build_tool_use_node(config: VerticalConfig):
    """Enriches `extracted_data` before generation, preferring a
    deterministic shortcut over spending an LLM call whenever possible.

    If `config.deterministic_enrichment` is set, it's called directly -
    zero LLM calls - since it exists specifically for enrichment that has
    no real judgment call to make (e.g. "always normalize every date").
    Otherwise, falls back to the generic LangChain tool-calling primitive:
    binds whatever `config.tools` supplies, executes whatever the model
    decides to call, and folds the results into state. This fallback path
    is what a vertical would use for enrichment that genuinely benefits
    from a model deciding what (if anything) to do. Verticals with neither
    configured skip this entirely at zero cost.
    """

    def use_tools(state: EngineState) -> dict:
        extracted = state.get("extracted_data", {})

        if config.deterministic_enrichment:
            updated = config.deterministic_enrichment(extracted)
            return {"extracted_data": updated} if updated != extracted else {}

        if not config.tools:
            return {}
        model = get_model_with_fallback(
            ModelTier.LIGHTWEIGHT, max_tokens=get_settings().max_tokens_tool_use
        )
        tool_model = model.bind_tools(config.tools)
        public_extracted = _public_extracted_data(extracted)
        tools_by_name = {getattr(t, "name", getattr(t, "__name__", "")): t for t in config.tools}

        prompt = (
            "You are preparing candidate data for a document-generation step. "
            "You have tools available to clean up or enrich this data (e.g. "
            "normalizing inconsistent dates, computing durations). Call any "
            "tools that would genuinely improve the data below - call none if "
            "nothing needs it. Do not explain yourself, just call tools if "
            "useful."
        )
        payload = json.dumps(public_extracted, ensure_ascii=False)

        try:
            response = invoke_with_retry(tool_model, [("system", prompt), ("human", payload)])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tool-use node: model call failed, skipping enrichment: %s", exc)
            return {}

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return {}

        enrichment: dict[str, Any] = {}
        for call in tool_calls:
            tool = tools_by_name.get(call.get("name"))
            if not tool:
                continue
            try:
                result = tool.invoke(call.get("args", {}))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tool-use node: tool '%s' failed: %s", call.get("name"), exc)
                continue
            key = f"{call.get('name')}::{call.get('id') or len(enrichment)}"
            enrichment[key] = {"tool": call.get("name"), "args": call.get("args", {}), "result": result}
            logger.info(
                "Tool-use node: model called '%s'(%s) -> %r",
                call.get("name"), call.get("args", {}), result,
            )

        if not enrichment:
            return {}

        merged = {
            **extracted,
            "tool_enrichment": {**extracted.get("tool_enrichment", {}), **enrichment},
        }
        return {"extracted_data": merged}

    return use_tools


def build_generation_node(config: VerticalConfig):
    def generate(state: EngineState) -> dict:
        settings = get_settings()
        prompt = config.generation_prompt.format(language=state.get("language", "en"))
        payload = json.dumps(_public_extracted_data(state.get("extracted_data", {})), ensure_ascii=False, sort_keys=True)
        previous_errors = state.get("validation_errors") or []
        if previous_errors and state.get("retry_count", 0) > 0:
            payload += (
                "\n\n[Previous attempt had these validation errors - fix them this "
                "time]: " + "; ".join(previous_errors)
            )

        cache_key = llm_cache.make_key("generate", config.name, prompt, payload)
        output = llm_cache.get(cache_key) if settings.llm_cache_enabled else None
        if output is not None:
            return {"structured_output": output}

        model = get_model_with_fallback(ModelTier.PRIMARY, max_tokens=settings.max_tokens_generate)
        # "function_calling" (tool-call based) rather than the default
        # provider-specific strict JSON-schema mode - the latter is an
        # OpenAI-native feature that Groq/Gemini's OpenAI-compat layers
        # don't implement, and this node's model can fall back onto either
        # of those (see app/llm/router.py) so it needs a method every link
        # in that chain actually supports.
        structured_model = model.with_structured_output(
            config.output_schema, method="function_calling"
        )

        try:
            result = invoke_with_retry(
                structured_model, [("system", prompt), ("human", payload)]
            )
            output = result.model_dump() if hasattr(result, "model_dump") else dict(result)
            if output and settings.llm_cache_enabled:
                llm_cache.put(
                    cache_key, output,
                    ttl_seconds=settings.llm_cache_ttl_seconds,
                    max_entries=settings.llm_cache_max_entries,
                )
            return {"structured_output": output}
        except Exception as exc:  # noqa: BLE001
            # Free-tier models occasionally emit JSON that's shaped correctly
            # but missing a required field (e.g. no job_title on one entry),
            # which makes structured-output parsing raise instead of just
            # returning bad data. Treat that the same as a validation
            # failure so the graph's existing retry-with-feedback loop
            # handles it, rather than crashing the whole request. Never
            # cached, so a retry of the identical payload gets a fresh
            # attempt instead of being locked into today's failure.
            logger.warning("Generation node: structured output parsing failed: %s", exc)
            return {"structured_output": None}

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
