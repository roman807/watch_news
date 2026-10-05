"""The two kinds of model call this project makes, behind one small interface,
so the same code can run on either backend:

- Anthropic (default): the Claude API, models as set in summarize.py /
  analyze.py. Needs ANTHROPIC_API_KEY. This is what the GitHub Actions
  workflow uses.
- OpenAI-compatible: any server speaking the OpenAI chat-completions API —
  e.g. Gallo24's agent, which forwards to Infomaniak's swiss-hosted models.
  Selected by setting OPENAI_BASE_URL, plus:
    WATCH_NEWS_SUMMARY_MODEL   model for the per-article summaries
    WATCH_NEWS_ANALYZE_MODEL   model for the cross-article analysis
    OPENAI_API_KEY             if the server needs one (any value otherwise)
"""

from __future__ import annotations

import json
import os


def make_client() -> "Client":
    """The backend selected by the environment; raises SystemExit with a
    helpful message if it isn't configured."""
    if os.environ.get("OPENAI_BASE_URL"):
        missing = [v for v in ("WATCH_NEWS_SUMMARY_MODEL", "WATCH_NEWS_ANALYZE_MODEL") if not os.environ.get(v)]
        if missing:
            raise SystemExit(f"OPENAI_BASE_URL is set, but {', '.join(missing)} isn't.")
        return OpenAICompatibleClient()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "No model backend configured: set ANTHROPIC_API_KEY (Claude), or OPENAI_BASE_URL + "
            "WATCH_NEWS_SUMMARY_MODEL + WATCH_NEWS_ANALYZE_MODEL (OpenAI-compatible) — "
            "or pass --dry-run to test without any model calls."
        )
    return AnthropicClient()


class Client:
    def complete(self, task: str, anthropic_model: str, prompt: str, max_tokens: int) -> str:
        """Plain text answer to a single user prompt."""
        raise NotImplementedError

    def forced_tool_call(self, task: str, anthropic_model: str, prompt: str, tool: dict, max_tokens: int) -> dict:
        """Makes the model call `tool` (Anthropic tool format: name,
        description, input_schema) and returns the call's arguments."""
        raise NotImplementedError


class AnthropicClient(Client):
    def __init__(self) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(self, task, anthropic_model, prompt, max_tokens):
        response = self._client.messages.create(
            model=anthropic_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()

    def forced_tool_call(self, task, anthropic_model, prompt, tool, max_tokens):
        # Streaming is required by the SDK at high max_tokens.
        with self._client.messages.stream(
            model=anthropic_model,
            max_tokens=max_tokens,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()
        return next(b for b in response.content if b.type == "tool_use").input


class OpenAICompatibleClient(Client):
    def __init__(self) -> None:
        from openai import OpenAI

        # Analysis of a full day's articles can take minutes.
        self._client = OpenAI(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ.get("OPENAI_API_KEY") or "unused",
            timeout=900,
        )
        self._models = {
            "summary": os.environ["WATCH_NEWS_SUMMARY_MODEL"],
            "analyze": os.environ["WATCH_NEWS_ANALYZE_MODEL"],
        }

    def complete(self, task, anthropic_model, prompt, max_tokens):
        response = self._client.chat.completions.create(
            model=self._models[task],
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()

    def forced_tool_call(self, task, anthropic_model, prompt, tool, max_tokens):
        response = self._client.chat.completions.create(
            model=self._models[task],
            max_tokens=max_tokens,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["input_schema"],
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": tool["name"]}},
            messages=[{"role": "user", "content": prompt}],
        )
        calls = response.choices[0].message.tool_calls or []
        call = next((c for c in calls if c.function.name == tool["name"]), None)
        if call is None:
            raise RuntimeError(
                f"Model didn't call {tool['name']} (finish_reason={response.choices[0].finish_reason})"
            )
        return json.loads(call.function.arguments)
