"""Gemini structured-output wrapper — the single LLM gateway for the app."""

import json
import logging
from typing import Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _get_client() -> genai.Client:
    """Create a Gemini client using the configured API key."""
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


async def complete_json(
    schema: Type[T],
    prompt: str,
    images: list[tuple[bytes, str]] | None = None,
    max_retries: int = 1,
) -> T:
    """
    Send a prompt (with optional images) to Gemini and parse the response
    into a Pydantic model.

    Args:
        schema: The Pydantic model class to validate against.
        prompt: The text prompt to send.
        images: Optional list of (image_bytes, mime_type) tuples.
        max_retries: Number of retries on validation failure.

    Returns:
        Validated Pydantic model instance.

    Raises:
        ValidationError: If response fails validation after all retries.
    """
    settings = get_settings()
    client = _get_client()

    # Build content parts
    contents: list[types.Part | str] = [prompt]
    if images:
        for img_bytes, mime_type in images:
            contents.append(
                types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            )

    # JSON schema for structured output
    json_schema = schema.model_json_schema()

    last_error: Exception | None = None

    for attempt in range(1 + max_retries):
        try:
            # If retrying, append error feedback
            retry_prompt = prompt
            if attempt > 0 and last_error:
                retry_prompt = (
                    f"{prompt}\n\n"
                    f"IMPORTANT: Your previous response failed validation with this error:\n"
                    f"{str(last_error)}\n"
                    f"Please fix the JSON output to conform to the schema."
                )
                contents[0] = retry_prompt

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=json_schema,
                    temperature=0.1,
                ),
            )

            # Parse JSON response
            raw_text = response.text
            if not raw_text:
                raise ValueError("Empty response from Gemini")

            parsed = json.loads(raw_text)
            result = schema.model_validate(parsed)
            return result

        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(
                f"Gemini response validation failed (attempt {attempt + 1}): {e}"
            )
            continue

    # All retries exhausted — raise the last error
    raise last_error  # type: ignore[misc]


async def complete_text(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> str:
    """
    Simple text completion (used for letter hardship paragraphs, etc.).
    No structured output — just returns a string.
    """
    settings = get_settings()
    client = _get_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )

    return response.text or ""
