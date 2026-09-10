# OpenAI-compatible chat client for prompt enhancement.
# Replaces the original LlamaCPP/GGUF backend: same magic-prompt template,
# sent as a system message; the query goes in as the user message.

import re

from openai import OpenAI

DEFAULT_BASE_URL = "http://localhost:8082/v1"
DEFAULT_MODEL = "qwen3.8-27b@q4_k_s:2"


def create_client(base_url=DEFAULT_BASE_URL, api_key="not-needed"):
    return OpenAI(base_url=base_url, api_key=api_key)


def build_messages(template_text, query_str):
    """Fill the magic-prompt template for a chat API.

    The original completion-style scaffolding (instruction_start / start_pattern /
    user_pattern / assistant_pattern markers) is dropped; the few-shot examples and
    instructions become the system message, the query becomes the user message.
    """
    system = template_text.format(
        instruction_start="",
        context_str="{context_str}",  # placeholder replaced by caller via .replace below
        start_pattern="",
        user_pattern="",
        assistant_pattern="",
        query_str=query_str,
    )
    return system


def enhance_prompt(client, model, template_name, query, context_str, temperature=0.7, max_tokens=16384):
    from .prompts import PROMPT_TEMPLATES

    template_text = PROMPT_TEMPLATES[template_name]
    # Fill everything except the context placeholder first, then splice in the
    # (possibly empty) RAG context so braces inside it can't break str.format.
    system = build_messages(template_text, query).replace("{context_str}", context_str or "")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Create a prompt for: {query}"},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def strip_thinking(output):
    """Drop any reasoning block (Qwen3 thinking mode) — the original stripped it too."""
    if '</think>' in output:
        output = re.sub(r".*?</think>", "", output, flags=re.DOTALL)
    return output
