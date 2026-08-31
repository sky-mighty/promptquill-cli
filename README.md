# Prompt Quill (CLI)

A minimal command-line version of [Prompt Quill](https://github.com/osi1880vr/prompt_quill):
type a short text-to-image prompt, get back a detailed enhanced one.

The core enhancement pipeline from the original app is kept — magic-prompt
templates, Qdrant RAG context retrieval, wildcard resolution and output cleanup —
but the Gradio UI, local GGUF/llama.cpp models and image-generation clients are gone.
The LLM now runs through any **OpenAI-compatible API** (default: `http://localhost:8082/v1`,
model `qwen3.8-27b@q4_k_s:2`).

## Install

```bash
cd prompt_quill
python3 -m venv .venv
.venv/bin/pip install -e .
```

This gives you the `prompt-quill` command (or use `.venv/bin/python -m prompt_quill`).

## Usage

```bash
prompt-quill "rocket man in space"
```

prints only the enhanced prompt on stdout, e.g. something like:

> High-quality digital art, ultra-detailed, professional, clear, high contrast, high saturation, vivid deep blacks, crystal clear, ((rocket man in space)), wearing a full helmet and leather jacket, leather gloves, standing in front of an advanced high-tech space rocket, surrounded by the vastness of outer space, with intense, vibrant colors, colorful, dark, modern art style, the rocket illuminated by the cosmic light, the rocketman standing solo against the cosmic backdrop, bokeh effect creating a blurry background, photography-style composition, on eye level, masterpiece.

Useful flags:

```
-n, --negative        also print the suggested negative prompt (and helpful models)
--template {a,b}      magic-prompt template: a = storytelling (default), b = concept lists
--temperature 0.7     sampling temperature
--max-tokens 512      max completion tokens
--model NAME          LLM model name        (env PQ_MODEL, default qwen3.8-27b@q4_k_s:2)
--base-url URL        OpenAI-compatible API base URL (env PQ_BASE_URL, default http://localhost:8082/v1)
--api-key KEY         API key              (env PQ_API_KEY, default "not-needed")

# RAG (Qdrant):
--qdrant-url URL      Qdrant server        (env QDRANT_URL, default http://localhost:6333)
--collection NAME     collection name      (default prompts_ng_gte)
--top-k N             similar prompts to retrieve (default 5)
--no-rag              skip retrieval, enhance without context

# extras:
--enhance             run keyword post-enhancement using wildcards/*.txt on the result
```

Wildcards in your input are resolved before the LLM call, same as the original app:
`prompt-quill "[red|blue] dragon"` or `__actor__ knight`.

## How it works

1. Input wildcards are resolved (`wildcards/`).
2. The query is embedded and the top-k most similar prompts are fetched from Qdrant;
   their texts become the RAG context, and any stored negative-prompt / model-name
   metadata is collected for the `-n` output.
3. The magic prompt template (few-shot examples included) is filled with your query +
   context and sent to the LLM as a chat request.
4. The response is cleaned of LLM artefacts (reasoning blocks, unbalanced brackets, …).

If Qdrant is unreachable or the collection does not exist, the tool prints a warning on
stderr and continues without context — it never fails because of RAG. Use `--no-rag` to
skip retrieval entirely (also avoids loading the embedding model).

## Setting up Qdrant (optional but recommended)

**Full step-by-step guide: [QDRANT_SETUP.md](QDRANT_SETUP.md)** — running a server,
loading the prebuilt ~3.2M-prompt dataset or indexing your own prompt files with
`scripts/index_prompts.py`, and verifying end-to-end.

In short: any collection named `prompts_ng_gte` (or pass `--collection`) whose points carry
the payload schema below works — each point's payload has `_node_content` (a JSON string
containing `"text"`) plus optional top-level `negative_prompt` and `model_name` metadata.

**Important:** this CLI embeds queries with **`BAAI/bge-base-en-v1.5`** (fixed, not
configurable). Your collection must have been indexed with that same model, or retrieval
quality degrades badly — the prebuilt dataset and `scripts/index_prompts.py` both use it.

## Notes

- The LLM endpoint is assumed to be running when you invoke the tool; connection errors
  are reported on stderr with exit code 1.
- `--enhance` appends keyword-based enhancements from `prompt_quill/wildcards/*.txt`
  (e.g. `actor.txt`, `actress.txt`) — an opt-in extra that was not part of the original
  core chat path either.
