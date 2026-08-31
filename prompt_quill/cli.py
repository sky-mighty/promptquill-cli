# prompt-quill: enhance short text-to-image prompts via an OpenAI-compatible LLM,
# with optional Qdrant RAG context (ported from the original Prompt Quill app).

import argparse
import os
import sys

from .llm import DEFAULT_BASE_URL, DEFAULT_MODEL, create_client, enhance_prompt, strip_thinking
from .prompts import DEFAULT_NEGATIVE_PROMPT
from .rag import DEFAULT_COLLECTION, DEFAULT_QDRANT_URL, RAGRetriever
from .wildcards import WildcardResolver, clean_llm_artefacts, get_negative_prompt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="prompt-quill",
        description="Enhance a short text-to-image prompt into a detailed one "
                    "(Prompt Quill core, CLI edition).",
    )
    parser.add_argument("prompt", help='the short prompt to enhance, e.g. "rocket man in space"')

    out = parser.add_argument_group("output")
    out.add_argument("-n", "--negative", action="store_true",
                     help="also print the suggested negative prompt and helpful models")

    llm = parser.add_argument_group("LLM (OpenAI-compatible API)")
    llm.add_argument("--base-url", default=os.environ.get("PQ_BASE_URL", DEFAULT_BASE_URL),
                     help=f"API base URL (default: {DEFAULT_BASE_URL}, env PQ_BASE_URL)")
    llm.add_argument("--model", default=os.environ.get("PQ_MODEL", DEFAULT_MODEL),
                     help=f"model name (default: {DEFAULT_MODEL}, env PQ_MODEL)")
    llm.add_argument("--api-key", default=os.environ.get("PQ_API_KEY", "not-needed"),
                     help="API key (default: not-needed, env PQ_API_KEY)")
    llm.add_argument("--temperature", type=float, default=0.7)
    llm.add_argument("--max-tokens", type=int, default=512)
    llm.add_argument("--template", choices=["a", "b"], default="a",
                     help="magic prompt template: a = storytelling (default), b = concept lists")

    rag = parser.add_argument_group("RAG (Qdrant)")
    rag.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL),
                     help=f"Qdrant URL (default: {DEFAULT_QDRANT_URL}, env QDRANT_URL)")
    rag.add_argument("--collection", default=DEFAULT_COLLECTION,
                     help=f"Qdrant collection (default: {DEFAULT_COLLECTION})")
    rag.add_argument("--top-k", type=int, default=5, help="number of similar prompts to retrieve")
    rag.add_argument("--no-rag", action="store_true",
                     help="skip Qdrant retrieval and enhance without context")

    ext = parser.add_argument_group("extras")
    ext.add_argument("--enhance", action="store_true",
                     help="run keyword post-enhancement (wildcard files in wildcards/) on the result")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    # Resolve input wildcards before sending to the LLM, as the original did.
    resolver = WildcardResolver(wildcards_dir=os.path.join(SCRIPT_DIR, "wildcards"))
    query = resolver.resolve_prompt(args.prompt)

    context_str = ""
    negative_list = []
    models_list = []
    if not args.no_rag:
#        try: # do not continue without RAG
        retriever = RAGRetriever(
            qdrant_url=args.qdrant_url,
            collection=args.collection,
            top_k=args.top_k,
        )
        context_str, negative_list, models_list = retriever.retrieve(query)
#        except Exception as e:
#            print(f"warning: RAG unavailable ({e.__class__.__name__}: {e}); "
#                  f"continuing without context", file=sys.stderr)

    try:
        client = create_client(base_url=args.base_url, api_key=args.api_key)
        raw = enhance_prompt(
            client=client,
            model=args.model,
            template_name=args.template,
            query=query,
            context_str=context_str,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except Exception as e:
        print(f"error: LLM request to {args.base_url} failed: {e}", file=sys.stderr)
        return 1

    output = strip_thinking(raw).strip()
    output = clean_llm_artefacts(output)
    if not output.strip():
        print("error: LLM returned an empty prompt", file=sys.stderr)
        return 1

    if args.enhance:
        from .enhance import PromptEnhance
        output = PromptEnhance().enhance_prompt(output)

    print(output)

    if args.negative:
        neg = get_negative_prompt(negative_list, DEFAULT_NEGATIVE_PROMPT)
        print(f"\nMaybe helpful negative prompt:\n\n{neg}")
        if models_list:
            print("\nMaybe helpful models:\n\n" + "\n".join(models_list))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
