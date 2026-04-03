"""gemini_client.py — Gemini LLM backend for Pokemon agent.

Implements the LLMClient protocol using Google's Generative AI SDK.
Uses Gemini 2.5 Flash by default (free tier: 15 RPM, 1M tokens/day).

Adapted from pokeagent-speedrun reference repo (STEAL CODE directive S218).

Usage:
    Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment.

    from gemini_client import GeminiClient
    client = GeminiClient()  # defaults to gemini-2.5-flash
    response = client.create_message(
        model="gemini-2.5-flash",
        max_tokens=1024,
        system="You are a Pokemon player.",
        messages=[{"role": "user", "content": "What do you see?"}],
        tools=[],
        temperature=0.0,
    )
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from agent import LLMResponse, ToolUse

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


def _normalize_tool_args(value: Any) -> Any:
    """Normalize Gemini function-call args into agent-friendly Python types."""
    if isinstance(value, dict):
        return {
            key: _normalize_tool_args(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_tool_args(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _json_schema_to_gemini_schema(schema: Any) -> Any:
    """Convert Anthropic/JSON Schema fragments into Gemini schema format."""
    if not isinstance(schema, dict):
        return schema

    converted = {}

    for key, value in schema.items():
        if key == "type":
            converted["type_"] = str(value).upper()
        elif key == "format":
            converted["format_"] = value
        elif key == "properties" and isinstance(value, dict):
            converted["properties"] = {
                name: _json_schema_to_gemini_schema(prop_schema)
                for name, prop_schema in value.items()
            }
        elif key == "items":
            converted["items"] = _json_schema_to_gemini_schema(value)
        elif key in {"description", "nullable", "enum", "required"}:
            converted[key] = value
        elif key in {"default", "title", "$schema", "$defs", "additionalProperties"}:
            # Gemini's deprecated SDK rejects many standard JSON Schema fields.
            continue

    return converted


def _anthropic_tool_to_gemini(tool: dict) -> dict:
    """Convert an Anthropic-format tool to Gemini function declaration.

    Anthropic format:
        {"name": "...", "description": "...", "input_schema": {...}}

    Gemini format:
        {"name": "...", "description": "...", "parameters": {...}}
    """
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": _json_schema_to_gemini_schema(tool.get("input_schema", {})),
    }


def _anthropic_tools_to_gemini(tools: Optional[list]) -> list:
    """Convert a list of Anthropic-format tools to Gemini function declarations."""
    if not tools:
        return []
    return [_anthropic_tool_to_gemini(t) for t in tools]


def _anthropic_messages_to_gemini(messages: list) -> list:
    """Convert Anthropic-style messages to Gemini content format.

    Anthropic: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    Gemini: [{"role": "user", "parts": ["..."]}, {"role": "model", "parts": ["..."]}]
    """
    gemini_messages = []
    tool_names_by_id = {}

    for msg in messages:
        role = "model" if msg.get("role") == "assistant" else "user"
        content = msg.get("content", "")

        # Handle content that's a list of blocks (Anthropic multimodal format)
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type")
                    if block_type == "text":
                        parts.append({"text": block["text"]})
                    elif block_type == "image":
                        source = block.get("source", {})
                        media_type = source.get("media_type", "image/png")
                        data = source.get("data")
                        if data:
                            parts.append({
                                "inline_data": {
                                    "mime_type": media_type,
                                    "data": base64.b64decode(data),
                                },
                            })
                    elif block_type == "tool_use":
                        tool_use_id = block.get("id", "")
                        tool_name = block.get("name", "")
                        if tool_use_id and tool_name:
                            tool_names_by_id[tool_use_id] = tool_name
                        parts.append({
                            "function_call": {
                                "id": tool_use_id,
                                "name": tool_name,
                                "args": block.get("input", {}),
                            },
                        })
                    elif block_type == "tool_result":
                        tool_use_id = block.get("tool_use_id", "")
                        result_content = block.get("content", "")
                        try:
                            response = json.loads(result_content)
                        except (TypeError, json.JSONDecodeError):
                            response = {"result": result_content}
                        parts.append({
                            "function_response": {
                                "id": tool_use_id,
                                "name": tool_names_by_id.get(tool_use_id, tool_use_id),
                                "response": response,
                            },
                        })
                    else:
                        parts.append({"text": str(block)})
                else:
                    parts.append({"text": str(block)})
            if parts:
                gemini_messages.append({"role": role, "parts": parts})
        else:
            gemini_messages.append({"role": role, "parts": [{"text": str(content)}]})

    return gemini_messages


class GeminiClient:
    """LLM client using Google Gemini API (free tier compatible).

    Implements the LLMClient protocol expected by the Pokemon agent.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        if genai is None:
            raise ImportError(
                "google-generativeai not installed. "
                "Run: pip install google-generativeai"
            )

        self.model_name = model_name
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError(
                "Gemini API key not found. "
                "Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
            )

        genai.configure(api_key=api_key)
        logger.info("GeminiClient initialized with model: %s", model_name)

    def create_message(
        self,
        model: str,
        max_tokens: int,
        system: str,
        messages: list,
        tools: list,
        temperature: float,
    ) -> LLMResponse:
        """Call Gemini API and return an LLMResponse.

        Translates Anthropic-style arguments to Gemini format,
        and converts the response back to our LLMResponse format.
        """
        # Build model with system instruction
        model_kwargs = {}
        if system:
            model_kwargs["system_instruction"] = system

        # Convert tools
        gemini_tools = _anthropic_tools_to_gemini(tools)
        if gemini_tools:
            model_kwargs["tools"] = gemini_tools

        gemini_model = genai.GenerativeModel(
            model or self.model_name,
            **model_kwargs,
        )

        # Convert messages
        gemini_messages = _anthropic_messages_to_gemini(messages)

        # Generation config
        gen_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        # Call the API
        response = gemini_model.generate_content(
            gemini_messages if gemini_messages else "Hello",
            generation_config=gen_config,
        )

        # Parse response
        text_parts = []
        tool_uses = []

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.function_call and part.function_call.name:
                    # Convert function_call args to regular dict
                    args = dict(part.function_call.args) if part.function_call.args else {}
                    tool_uses.append(ToolUse(
                        id=f"gemini-{uuid.uuid4().hex[:8]}",
                        name=part.function_call.name,
                        input=_normalize_tool_args(args),
                    ))
                elif part.text:
                    text_parts.append(part.text)

        # Extract usage
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0)
        output_tokens = getattr(usage, "candidates_token_count", 0)

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else "",
            tool_uses=tool_uses,
            stop_reason="tool_use" if tool_uses else "end_turn",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
