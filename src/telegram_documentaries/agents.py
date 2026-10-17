"""Shared plumbing for calling an ADK LlmAgent that returns structured (Pydantic) output.

Each call runs in a throwaway ADK session, deleted afterwards: our own SessionStore is
the single source of truth for conversation state.
"""

import asyncio

from google.adk.runners import Runner
from google.genai import types
from pydantic import BaseModel, ValidationError


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
    sessions = runner.session_service
    session = await sessions.create_session(app_name=runner.app_name, user_id=user_id)
    message = types.Content(role="user", parts=parts)
    try:
        text = await asyncio.wait_for(
            _final_text(runner, user_id, session.id, message, error), timeout=timeout_s
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

    try:
        return schema.model_validate_json(text)
    except ValidationError as exc:
        raise error(f"model output did not match {schema.__name__}") from exc


async def _final_text(
    runner: Runner,
    user_id: str,
    session_id: str,
    message: types.Content,
    error: type[AgentCallError],
) -> str:
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
            return "".join(part.text or "" for part in event_parts)
    raise error("agent finished without a final response")
