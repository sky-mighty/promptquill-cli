# AGENTS.md — prompt_quill (CLI)

Minimal CLI port of [Prompt Quill](https://github.com/osi1880vr/prompt_quill): type a short
text-to-image prompt, get back an enhanced one. This repo is **self-contained** — do not
touch anything outside `prompt_quill/` in the bookfactory workspace (bookfactory has its own
`.venv`; never use it for this project).

## Layout

```
prompt_quill/            # Python package (installed editable into .venv)
├── cli.py               # argparse entry point; main() — flags, env vars, output flow
├── llm.py               # OpenAI-compatible client; template fill-in; strip_thinking()
├── prompts.py           # magic-prompt few-shot templates a/b + DEFAULT_NEGATIVE_PROMPT (verbatim from upstream)
├── rag.py               # RAGRetriever: QdrantClient + SentenceTransformer, ports the original read path
├── wildcards.py         # WildcardResolver + clean_llm_artefacts() + get_negative_prompt() (ported verbatim)
├── enhance.py           # opt-in --enhance keyword post-processing
└── wildcards/*.txt      # wildcard data files for __name__ resolution and --enhance
scripts/index_prompts.py # standalone: index a folder of .txt/.md prompts into Qdrant (no llama-index)
QDRANT_SETUP.md          # step-by-step Qdrant setup guide (keep in sync with rag.py / cli.py behavior)
```

## Running it

Always use this repo's venv, never the system python or bookfactory's:

```bash
cd prompt_quill
.venv/bin/prompt-quill "rocket man in space"          # enhanced prompt on stdout only
.venv/bin/prompt-quill -n "..."                       # + suggested negative prompt / models
.venv/bin/python scripts/index_prompts.py <dir>       # index own prompts into Qdrant
```

- LLM: OpenAI-compatible API at `http://localhost:8082/v1` (env `PQ_BASE_URL`), model
  `qwen3.8-27b@q4_k_s:2` (env `PQ_MODEL`). It is a **shared, slow** endpoint — expect ~2–3 min
  per call; don't loop calls in tests. Assume it's running when the tool is invoked.
- Qdrant: `http://localhost:6333` (env `QDRANT_URL`), collection default `prompts_ng_gte`.

## Invariants — do not break these

1. **Payload schema** (`rag.py` reads, `scripts/index_prompts.py` writes): each point's
   payload has `_node_content` = a JSON *string* containing `{"text": ...}`, plus optional
   top-level `negative_prompt` (comma-separated) and `model_name`. This matches what the
   original llama-index pipeline wrote; changing it breaks compatibility with existing
   collections.
2. **Fixed embedding model**: `BAAI/bge-base-en-v1.5` is hardcoded in both
   `rag.py` (`EMBED_MODEL`) and `scripts/index_prompts.py` — there is deliberately no
   override flag, so query-time and index-time models always match by construction. The
   prebuilt ~3.2M-prompt dataset was indexed with this model too. A collection indexed
   with any other model will silently degrade retrieval; re-index it rather than adding a
   flag back. Keep the two `EMBED_MODEL` constants in sync if they ever change.
3. **Graceful RAG degradation**: a missing/unreachable Qdrant must warn on stderr and
   continue without context — never hard-fail because of RAG (`cli.py` try/except).
4. **stdout purity**: the enhanced prompt is the only thing printed to stdout (pipe-friendly);
   all diagnostics, progress, warnings go to stderr.
5. `prompts.py` templates and `clean_llm_artefacts()` are verbatim ports of upstream quality
   assets — change them deliberately, not incidentally.

## Conventions

- Python 3.14; deps in `pyproject.toml`: openai, qdrant-client, sentence-transformers (+torch).
  No llama-index (incompatible with this Python) — RAG is implemented directly on
  qdrant-client + sentence-transformers. Keep it that way.
- Lazy imports for heavy deps (`qdrant_client`, `sentence_transformers`) inside methods so
  `--no-rag` runs never load the embedding model.
- Wildcard syntax (ported from upstream): `{a|b}` = random choice, `[a, b]` = inline options,
  `__name__` = file wildcard from `wildcards/`. Don't "fix" this to match other tools' syntax.

## Testing notes

- No test suite; verify by running the CLI. A full RAG check needs a live Qdrant — see
  `QDRANT_SETUP.md`; for throwaway tests use the standalone binary in /tmp and clean up
  (port 6333 must be free afterwards).
- The LLM endpoint is shared and flaky; if calls time out, wait and retry rather than
  changing code.
