# Qdrant retrieval for prompt context, negative prompts and model names.
# Ports the read path of the original Prompt Quill (llama_index_interface.py:
# get_context_text / prepare_meta_data_from_nodes) directly on qdrant-client +
# sentence-transformers, without the llama-index dependency.

import json
import sys

DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "test_collection_import"
# Fixed embedding model — no override. Must match the model used when indexing;
# the prebuilt dataset and scripts/index_prompts.py both use this one.
EMBED_MODEL = "BAAI/bge-base-en-v1.5"


class RAGRetriever:
    def __init__(self, qdrant_url=DEFAULT_QDRANT_URL, collection=DEFAULT_COLLECTION, top_k=5):
        self.qdrant_url = qdrant_url
        self.collection = collection
        self.top_k = top_k
        self._client = None
        self._embedder = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            try:
                self._client = QdrantClient(url=self.qdrant_url, timeout=60, check_compatibility=False)
            except TypeError:  # older qdrant-client without this parameter
                self._client = QdrantClient(url=self.qdrant_url, timeout=60)
        return self._client

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            print(f"Loading embedding model {EMBED_MODEL} ...", file=sys.stderr, flush=True)
            self._embedder = SentenceTransformer(EMBED_MODEL)
        return self._embedder

    def retrieve(self, query):
        """Return (context_text, negative_prompt_list, models_list).

        Raises on connection/collection errors; the caller degrades gracefully.
        """
        client = self._get_client()
        # Cheap connectivity check before paying for the embedding model download/load.
        try:
            client.get_collections()
        except Exception as e:
            raise ConnectionError(f"cannot reach Qdrant at {self.qdrant_url}") from e

        embedder = self._get_embedder()

        vector = embedder.encode(query, normalize_embeddings=True).tolist()
        if hasattr(client, "query_points"):  # qdrant-client >= 1.7 / 2.x
            result = client.query_points(
                collection_name=self.collection,
                query=vector,
                limit=self.top_k,
            ).points
        else:  # legacy API
            result = client.search(
                collection_name=self.collection,
                query_vector=vector,
                limit=self.top_k,
            )

        context_texts = []
        negative_prompts = []
        models_list = []
        for point in result:
            payload = point.payload or {}
            # llama-index QdrantVectorStore schema: _node_content is a JSON string
            node_content = payload.get('_node_content')
            if isinstance(node_content, str):
                try:
                    text = json.loads(node_content).get('text', '')
                except (json.JSONDecodeError, AttributeError):
                    text = ''
            elif isinstance(node_content, dict):
                text = node_content.get('text', '')
            else:
                text = payload.get('text', '')
            if text and text not in context_texts:
                context_texts.append(text)

            neg = payload.get('negative_prompt')
            if neg is not None:
                negative_prompts.extend(part.strip() for part in neg.split(',') if part.strip())
            model_name = payload.get('model_name')
            if model_name:
                models_list.append(str(model_name))

        # dedupe, preserving order (set() would scramble the negative-prompt order)
        return "\n".join(context_texts), list(dict.fromkeys(negative_prompts)), list(dict.fromkeys(models_list))
