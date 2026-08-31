#!/usr/bin/env python3
"""Index prompt files into a Qdrant collection for the prompt-quill CLI.

Each non-empty .txt/.md file becomes one point whose payload matches exactly
what prompt_quill/rag.py reads:

    _node_content  = JSON string containing {"text": <prompt text>}
    negative_prompt = optional, comma-separated (from a "## negative:" header line)
    model_name      = optional (from a "## model:" header line)

Header lines are stripped from the embedded text. Point IDs are UUID5s of the
file path, so re-running the script updates points instead of duplicating them.

Usage:
    .venv/bin/python scripts/index_prompts.py /path/to/prompts/ \
        [--qdrant-url http://localhost:6333] [--collection test_collection_import] \
        [--vector-size 768]

The embedding model is fixed to BAAI/bge-base-en-v1.5 — the same one prompt-quill
queries with, so no extra flag is needed at query time.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "test_collection_import"
# Fixed embedding model — must match prompt_quill/rag.py's EMBED_MODEL.
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
DEFAULT_VECTOR_SIZE = 768  # correct for bge-base-en-v1.5

HEADER_PREFIXES = ("## negative:", "## model:")


def parse_file(path: Path):
    """Return (text, negative_prompt, model_name) from one prompt file."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    text_lines = []
    negative = None
    model = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(HEADER_PREFIXES[0]):
            value = stripped[len(HEADER_PREFIXES[0]):].strip()
            if value:
                negative = value
        elif stripped.startswith(HEADER_PREFIXES[1]):
            value = stripped[len(HEADER_PREFIXES[1]):].strip()
            if value:
                model = value
        else:
            text_lines.append(line)
    text = "\n".join(text_lines).strip()
    return text, negative, model


def collect_files(input_path: Path):
    if input_path.is_file():
        return [input_path]
    files = sorted(
        p for p in input_path.rglob("*")
        if p.is_file() and p.suffix.lower() in (".txt", ".md")
    )
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="a prompt file, or a directory of .txt/.md prompt files")
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--vector-size", type=int, default=DEFAULT_VECTOR_SIZE)
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"error: {input_path} does not exist", file=sys.stderr)
        return 1

    files = collect_files(input_path)
    parsed = []
    for f in files:
        text, negative, model = parse_file(f)
        if text:
            rel = str(f.relative_to(input_path)) if input_path.is_dir() else f.name
            parsed.append((uuid.uuid5(uuid.NAMESPACE_URL, rel), f, text, negative, model))
    if not parsed:
        print("error: no non-empty .txt/.md prompt files found", file=sys.stderr)
        return 1

    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from sentence_transformers import SentenceTransformer

    client = QdrantClient(url=args.qdrant_url, timeout=60, check_compatibility=False)
    try:
        existing = {c.name for c in client.get_collections().collections}
    except Exception as e:
        print(f"error: cannot reach Qdrant at {args.qdrant_url}: {e}", file=sys.stderr)
        return 1

    if args.collection not in existing:
        client.create_collection(
            collection_name=args.collection,
            vectors_config=VectorParams(size=args.vector_size, distance=Distance.COSINE),
        )
        print(f"created collection {args.collection} ({args.vector_size}-dim cosine)", file=sys.stderr)

    print(f"Loading embedding model {EMBED_MODEL} ...", file=sys.stderr, flush=True)
    embedder = SentenceTransformer(EMBED_MODEL)

    batch = 64
    for i in range(0, len(parsed), batch):
        chunk = parsed[i:i + batch]
        vectors = embedder.encode([t for _, _, t, _, _ in chunk], normalize_embeddings=True).tolist()
        points = []
        for (pid, f, text, negative, model), vector in zip(chunk, vectors):
            payload = {"_node_content": json.dumps({"text": text})}
            if negative:
                payload["negative_prompt"] = negative
            if model:
                payload["model_name"] = model
            points.append(PointStruct(id=str(pid), vector=vector, payload=payload))
        client.upsert(collection_name=args.collection, points=points)
        print(f"  indexed {min(i + batch, len(parsed))}/{len(parsed)}", file=sys.stderr)

    with_neg = sum(1 for p in parsed if p[3])
    with_model = sum(1 for p in parsed if p[4])
    print(f"\nDone: {len(parsed)} points in '{args.collection}' "
          f"({with_neg} with negative prompt, {with_model} with model name).", file=sys.stderr)
    print("Next step:", file=sys.stderr)
    print('  prompt-quill -n "your short prompt"', file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
