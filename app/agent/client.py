"""Thin OpenAI Responses wrapper that returns a parsed Pydantic model."""

from __future__ import annotations

import logging
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.config.settings import Settings

T = TypeVar("T", bound=BaseModel)

log = logging.getLogger("digest.agent")


def openai_client(settings: Settings) -> OpenAI:
    return OpenAI(api_key=settings.require_openai_api_key())


def parse_response(
    model: str,
    instructions: str,
    user_input: str,
    schema: type[T],
    client: OpenAI,
) -> T:
    log.debug(
        "model=%s schema=%s input_chars=%d",
        model,
        schema.__name__,
        len(user_input),
    )
    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=user_input,
        text_format=schema,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError(f"{model} returned no parsed {schema.__name__}")
    return parsed
