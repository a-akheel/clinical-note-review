"""Provider adapters return validated notes; they do not approve clinical content."""

import json
import os
import httpx
from pydantic import ValidationError
from .prompts import PROMPTS
from .schemas import Note

SECTIONS = ("subjective", "objective", "assessment", "plan")


class GenerationError(Exception):
    pass


async def openai_generate(turns, version):
    key, model = os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL")
    if not key or not model:
        raise GenerationError(
            "Live mode needs OPENAI_API_KEY and OPENAI_MODEL configured on the server."
        )
    # Pydantic validation constraints are enforced locally; keep the provider schema minimal.
    claim = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "source_turn_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["text", "source_turn_ids"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {s: {"type": "array", "items": claim} for s in SECTIONS},
        "required": list(SECTIONS),
        "additionalProperties": False,
    }
    payload = {
        "model": model,
        "store": False,
        "instructions": PROMPTS[version],
        "input": json.dumps({"synthetic_transcript": turns}),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "soap_note",
                "strict": True,
                "schema": schema,
            }
        },
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        if response.status_code != 200:
            raise GenerationError(
                f"Model provider returned HTTP {response.status_code}. Check server credentials, model access, and quota."
            )
        data = response.json()
        if data.get("status") != "completed":
            raise GenerationError("Model response was incomplete. No draft was saved.")
        blocks = [c for item in data.get("output", []) for c in item.get("content", [])]
        if any(c.get("type") == "refusal" for c in blocks):
            raise GenerationError("The model declined this input. No draft was saved.")
        content = "".join(
            c.get("text", "") for c in blocks if c.get("type") == "output_text"
        )
        note = Note.model_validate_json(content)
        return note, data.get("usage", {}), model
    except (httpx.HTTPError, json.JSONDecodeError, ValidationError) as exc:
        raise GenerationError(
            "The live request failed or returned an invalid note. No draft was saved."
        ) from exc


async def ollama_generate(turns, version):
    model = "qwen3:4b"
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": PROMPTS[version]},
            {"role": "user", "content": json.dumps({"synthetic_transcript": turns})},
        ],
        "format": Note.model_json_schema(),
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048},
        "keep_alive": "5m",
    }
    try:
        async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/chat", json=payload
            )
        if response.status_code != 200:
            raise GenerationError(
                "Local model unavailable. Start ./run-ollama.sh and download qwen3:4b."
            )
        data = response.json()
        if not data.get("done") or data.get("done_reason") == "length":
            raise GenerationError(
                "Local model output was incomplete. No draft was saved."
            )
        note = Note.model_validate_json(data["message"]["content"])
        usage = {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
        }
        return note, usage, model
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise GenerationError(
            "Local model connection or output validation failed. Check Ollama is running. No draft was saved."
        ) from exc
