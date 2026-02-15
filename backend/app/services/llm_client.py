"""LLM gateway — CommonStack (OpenAI-compatible) or Gemini."""

import base64
import json
import logging
from typing import Any, Type, TypeVar

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# CommonStack vision supports these MIME types; PDFs are not sent as image parts.
COMMONSTACK_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _get_client() -> genai.Client:
    """Create a Gemini client using the configured API key."""
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _build_commonstack_content(
    prompt: str,
    images: list[tuple[bytes, str]] | None = None,
) -> str | list[dict[str, Any]]:
    """Build user message content in OpenAI format.

    If no images, returns a plain string. With images, returns a list of
    content parts using OpenAI's multimodal format (image_url with data URIs).
    """
    if not images:
        return prompt

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_bytes, mime_type in images:
        if mime_type in COMMONSTACK_IMAGE_MIME_TYPES:
            b64_data = base64.standard_b64encode(img_bytes).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{b64_data}",
                },
            })
    return content


def _extract_text_from_commonstack_response(body: dict) -> str:
    """Get assistant text from CommonStack (OpenAI-compatible) chat completions response."""
    choices = body.get("choices") or []
    if not choices:
        raise ValueError(f"No choices in CommonStack response. Full body keys: {list(body.keys())}")
    message = choices[0].get("message") or {}
    text = message.get("content") or ""
    if not text:
        raise ValueError(f"Empty content in CommonStack response message. Message keys: {list(message.keys())}")
    return text


def _extract_json_from_text(text: str) -> str:
    """Extract JSON from a model response that may include markdown fences or extra text.

    Handles:
      - ```json ... ```
      - ``` ... ```
      - Raw JSON (returns as-is if it starts with { or [)
      - JSON embedded in surrounding text (finds first { ... last })
    """
    import re

    stripped = text.strip()

    # Try stripping markdown code fences: ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", stripped, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Already looks like raw JSON
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    # Find the first { and last } as a fallback
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        return stripped[first_brace : last_brace + 1]

    # Give up — return as-is and let json.loads raise a clear error
    return stripped


async def _commonstack_complete_json(
    schema: Type[T],
    prompt: str,
    images: list[tuple[bytes, str]] | None = None,
    max_retries: int = 1,
) -> T:
    """Call CommonStack chat/completions with JSON output; return validated Pydantic model."""
    settings = get_settings()
    url = settings.commonstack_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.commonstack_api_key}",
        "Content-Type": "application/json",
    }
    logger.info("CommonStack complete_json → POST %s  model=%s", url, settings.commonstack_model)
    json_schema = schema.model_json_schema()
    last_error: Exception | None = None
    raw_text = ""

    for attempt in range(1 + max_retries):
        try:
            retry_prompt = prompt
            if attempt > 0 and last_error:
                retry_prompt = (
                    f"{prompt}\n\n"
                    f"IMPORTANT: Your previous response failed validation with this error:\n"
                    f"{str(last_error)}\n"
                    f"Please fix the JSON output to conform to the schema."
                )

            # Append schema to prompt so the model knows the target shape
            schema_prompt = (
                f"{retry_prompt}\n\n"
                f"You MUST respond with ONLY valid JSON matching this schema:\n"
                f"{json.dumps(json_schema, indent=2)}"
            )

            content = _build_commonstack_content(schema_prompt, images)
            payload: dict[str, Any] = {
                "model": settings.commonstack_model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": content}],
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                logger.error(
                    "CommonStack API error: status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
                raise ValueError(
                    f"CommonStack API error: {response.status_code} - {response.text[:200]}"
                )
            resp_body = response.json()
            logger.debug("CommonStack raw response: %s", json.dumps(resp_body, default=str)[:1000])
            raw_text = _extract_text_from_commonstack_response(resp_body)
            if not raw_text:
                raise ValueError("Empty text in CommonStack response")
            logger.debug("CommonStack content text (first 500 chars): %s", raw_text[:500])
            cleaned_json = _extract_json_from_text(raw_text)
            parsed = json.loads(cleaned_json)
            return schema.model_validate(parsed)
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(
                "CommonStack JSON response validation failed (attempt %s): %s  |  raw_text[:200]=%s",
                attempt + 1,
                e,
                raw_text[:200],
            )
            continue
    raise last_error  # type: ignore[misc]


async def _commonstack_complete_text(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> str:
    """Call CommonStack chat/completions for plain text completion."""
    settings = get_settings()
    url = settings.commonstack_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.commonstack_api_key}",
        "Content-Type": "application/json",
    }
    logger.info("CommonStack complete_text → POST %s  model=%s", url, settings.commonstack_model)
    payload: dict[str, Any] = {
        "model": settings.commonstack_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        logger.error(
            "CommonStack API error: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise ValueError(
            f"CommonStack API error: {response.status_code} - {response.text[:200]}"
        )
    text = _extract_text_from_commonstack_response(response.json())
    return text or ""


async def complete_json(
    schema: Type[T],
    prompt: str,
    images: list[tuple[bytes, str]] | None = None,
    max_retries: int = 1,
) -> T:
    """
    Send a prompt (with optional images) to the configured LLM and parse the response
    into a Pydantic model. Uses CommonStack if llm_provider is "commonstack" and key
    is set; otherwise Gemini.
    """
    settings = get_settings()
    if settings.llm_provider == "commonstack" and settings.commonstack_api_key:
        return await _commonstack_complete_json(
            schema=schema,
            prompt=prompt,
            images=images,
            max_retries=max_retries,
        )

    # Gemini path
    client = _get_client()
    contents: list[types.Part | str] = [prompt]
    if images:
        for img_bytes, mime_type in images:
            contents.append(
                types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            )
    json_schema = schema.model_json_schema()
    last_error: Exception | None = None

    for attempt in range(1 + max_retries):
        try:
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
    raise last_error  # type: ignore[misc]


async def complete_text(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> str:
    """
    Simple text completion (used for letter hardship paragraphs, etc.).
    Uses CommonStack if llm_provider is "commonstack" and key is set; otherwise Gemini.
    """
    settings = get_settings()
    if settings.llm_provider == "commonstack" and settings.commonstack_api_key:
        return await _commonstack_complete_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

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
