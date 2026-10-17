"""Shared plumbing for calling ADK LlmAgents: structured (Pydantic) or image output.

Each call runs in a throwaway ADK session, deleted afterwards: our own SessionStore is
the single source of truth for conversation state.
"""

import asyncio

from google.adk.runners import Runner
from google.genai import types
from pydantic import BaseModel, ValidationError

from telegram_documentaries.media import PortraitImage

MAX_ERROR_TEXT = 200


class AgentCallError(Exception):
    """An agent call produced no valid result (timeout, API error, bad output)."""


async def run_structured_agent[M: BaseModel](
    runner: Runner,
    *,
    user_id: str,
    parts: list[types.Part],
    schema: type[M],
    error: type[AgentCallError],
    timeout_s: float,
) -> M:
    """Send `parts` as one user message and validate the final response against `schema`.

    Every failure is raised as `error` (with the original exception as its cause).
    """
    final_parts = await _run(runner, user_id, parts, error, timeout_s)
    text = _text_of(final_parts)
    try:
        return schema.model_validate_json(text)
    except ValidationError as exc:
        raise error(f"model output did not match {schema.__name__}") from exc


async def run_image_agent(
    runner: Runner,
    *,
    user_id: str,
    parts: list[types.Part],
    error: type[AgentCallError],
    timeout_s: float,
) -> PortraitImage:
    """Send `parts` as one user message and return the first image in the final response.

    A response without an image (e.g. a refusal) raises `error` quoting the model's text.
    """
    final_parts = await _run(runner, user_id, parts, error, timeout_s)
    for part in final_parts:
        blob = part.inline_data
        if blob is not None and blob.data:
            try:
                return PortraitImage.model_validate(
                    {"data": blob.data, "mime_type": blob.mime_type}
                )
            except ValidationError as exc:
                raise error("model output did not match PortraitImage") from exc
    text = _text_of(final_parts)[:MAX_ERROR_TEXT]
    raise error(f"model returned no image: {text!r}")


def _text_of(parts: list[types.Part]) -> str:
    return "".join(part.text or "" for part in parts)


async def _run(
    runner: Runner,
    user_id: str,
    parts: list[types.Part],
    error: type[AgentCallError],
    timeout_s: float,
) -> list[types.Part]:
    """Run one turn in a throwaway session and return the final response's parts."""
    sessions = runner.session_service
    session = await sessions.create_session(app_name=runner.app_name, user_id=user_id)
    message = types.Content(role="user", parts=parts)
    try:
        return await asyncio.wait_for(
            _final_parts(runner, user_id, session.id, message, error), timeout=timeout_s
        )
    except TimeoutError as exc:
        raise error(f"timed out after {timeout_s}s") from exc
    except AgentCallError:
        raise
    except Exception as exc:
        raise error(f"model call failed: {exc!r}") from exc
    finally:
        await sessions.delete_session(
            app_name=runner.app_name, user_id=user_id, session_id=session.id
        )


async def _final_parts(
    runner: Runner,
    user_id: str,
    session_id: str,
    message: types.Content,
    error: type[AgentCallError],
) -> list[types.Part]:
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        # ADK reports model/API failures (bad key, quota, safety block) as error events.
        if event.error_code or event.error_message:
            raise error(f"model error {event.error_code}: {event.error_message}")
        if event.is_final_response():
            event_parts = event.content.parts if event.content else None
            if not event_parts:
                raise error("final response had no content")
            return list(event_parts)
    raise error("agent finished without a final response")
