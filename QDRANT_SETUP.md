# IMPORTANT:
**Use Qdrant v1.15.0 — not the latest.** RocksDB support was dropped in a later version,
and the prebuilt dataset (Path A) requires it to load. There is a way to upgrade the
dataset, but using v1.15.0 is far easier. Both options below are pinned to that version;
don't "fix" them to latest.

The following is courtesy of Qwen3.8-27b.

# Setting up Qdrant (step-by-step)

This guide gets the RAG layer of `prompt-quill` working from scratch, assuming you have
never used Qdrant before. It has two independent parts:

1. **Run a Qdrant server** (a small program that stores and searches vectors).
2. **Put prompt data into it** — either load the prebuilt ~3.2M-prompt collection
   (Path A, recommended) or index your own prompt files (Path B).

Until both are done, `prompt-quill` still works — it just prints a warning on stderr and
enhances without RAG context. Nothing here is required for basic use; it only improves
quality by giving the LLM similar real prompts as examples.

## What Qdrant actually does (30-second version)

Qdrant is a *vector database*. Every text can be turned into a list of numbers (a
*vector*) that captures its meaning — texts with similar meanings get nearby vectors.
We store millions of prompt texts as vectors, and when you run `prompt-quill "rocket man
in space"`, the tool turns your query into a vector too and asks Qdrant: *"which stored
prompts are closest to this one?"* The top few come back as context for the LLM.

Two things must be right for that to work, or you get garbage results:

- **The server** must be running (default `http://localhost:6333`).
- **The collection's data** must have been indexed with the same embedding model the CLI
  uses — `BAAI/bge-base-en-v1.5`, which is fixed in the code and cannot be changed.
  Different models produce vectors in different "spaces" — a collection indexed with any
  other model will retrieve silently (no error, just bad context). The prebuilt dataset
  (Path A) and the helper script (Path B) both use this model, so you never have to think
  about it.

## Step 0 — prerequisites

- A few GB of free disk for the server; ~10–20 GB if you load the full prebuilt collection.
- Ports **6333** (API) and **6334** (web UI) free on localhost. Check with:
  ```bash
  ss -ltnp | grep -E ':(6333|6334)'   # Linux; empty output = ports are free
  lsof -i :6333                       # macOS alternative
  ```

## Step 1 — run a Qdrant server

Pick **one** of the two options below. Both keep data on disk, so it survives restarts.

### Option A: Docker (easiest if you have Docker)

```bash
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:v1.15.0
```

- The tag is pinned to **v1.15.0** on purpose (see the IMPORTANT note at the top) — do not
  use `latest`.

- `-d` runs it in the background; `--name qdrant` lets you stop/remove it later.
- The named volume `qdrant_storage` is where Qdrant keeps its data — it survives
  `docker rm`. To start it again after a reboot: `docker start qdrant`.
- Stop it with `docker stop qdrant`; remove (keeping data) with `docker rm qdrant`.

> If Docker says the daemon isn't running, start it first: `sudo systemctl start docker`
> (or enable it: `sudo systemctl enable --now docker`).

### Option B: standalone binary (no Docker needed)

```bash
mkdir -p ~/qdrant && cd ~/qdrant
curl -sL https://github.com/qdrant/qdrant/releases/download/v1.15.0/qdrant-x86_64-unknown-linux-gnu.tar.gz | tar xz
cat > config.yaml <<'EOF'
storage:
  storage_path: ./storage
api:
  http_port: 6333
  enable_cors: true
EOF
./qdrant --config-path config.yaml
```

This runs in the foreground (Ctrl-C stops it). Data lives in `~/qdrant/storage`. To run it
in the background instead: append `nohup ... &` or use a systemd unit.

> The link above is for **x86_64 Linux**. On other platforms (macOS, ARM) use the Docker
> option instead — Qdrant publishes images for all major architectures.

### Verify the server is up

```bash
curl http://localhost:6333/collections
# → { "result": { "collections": [] }, "status": "ok", ... }
```

An empty list is correct at this point — no data yet. You can also open the web UI at
**http://localhost:6334** to browse collections and points visually (handy for checking
that your data loaded).

## Step 2 — get prompt data into Qdrant

Pick **one** path. Both produce a collection named `prompts_ng_gte` that the CLI reads by
default, so no extra flags are needed afterwards — both paths index with the same fixed
embedding model (`BAAI/bge-base-en-v1.5`) the CLI queries with.

### Path A — load the prebuilt ~3.2M-prompt collection (recommended)

The original Prompt Quill project ships its full indexed dataset as a download. This skips
all indexing work and gives you the same context quality the original app had.

1. Download it:
   ```bash
   curl -L -o data.zip "https://civitai.com/api/download/models/567736"
   ```
2. Inspect what's inside before doing anything else:
   ```bash
   unzip -l data.zip | head -40
   ```
3. Extract it somewhere with room to spare (the archive is ~16 GB; extracted data takes
   tens of GB):
   ```bash
   mkdir -p ~/qdrant_data && cd ~/qdrant_data
   unzip /path/to/data.zip
   ls
   ```

4. Load the contents into Qdrant — which method you need depends on what `ls` showed:

   **Most likely: a directory tree** (a ready-made Qdrant *storage* folder, usually with a
   `collections/` subdirectory). Replace your server's storage with it:
   1. Stop Qdrant (`docker stop qdrant`, or Ctrl-C for the binary).
   2. Swap the empty storage directory for the extracted one:
      - **binary install:** move the old empty storage aside and put the extracted tree in its place:
        `mv ~/qdrant/storage ~/qdrant/empty_storage && mv <extracted dir> ~/qdrant/storage`
      - **docker with a named volume:** the easiest way is to recreate the container using a
        bind mount instead, e.g.
        `docker rm qdrant && docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v $PWD/qdrant_data/<extracted dir>:/qdrant/storage qdrant/qdrant`
   3. Start Qdrant again — it loads the existing data on startup, no import step needed.

   **If instead you see `.snapshot` files** (e.g. `prompts_ng_gte.snapshot`): stop Qdrant,
   copy each `.snapshot` file into your server's storage directory under a `snapshots/`
   subfolder (`storage/snapshots/`), start Qdrant, then trigger the restore per file:
   ```bash
   curl -X POST http://localhost:6333/collections/prompts_ng_gte/snapshots \
        -H "Content-Type: application/json" \
        -d '{"location": "local", "snapshot_path": "/qdrant/storage/snapshots/<file>.snapshot"}'
   ```
   (For docker, use the in-container path `/qdrant/...`; for the binary install, any absolute
   path works.) The restore runs as a background job — watch it finish in the web UI or via
   `curl http://localhost:6333/collections/prompts_ng_gte/snapshots`, then confirm with
   `curl http://localhost:6333/collections`.

5. If the loaded collection turns out to be named something other than `prompts_ng_gte`,
   just pass it at query time: `prompt-quill --collection <name> ...` (check names in the
   web UI or via the collections endpoint).

### Path B — index your own prompt files

If you have a folder of prompts (one per file, `.txt` or `.md`) and want to build your
own collection instead. The helper script `scripts/index_prompts.py` does everything: it
embeds each file with the same fixed embedding model the CLI queries with
(`BAAI/bge-base-en-v1.5`), creates the collection if missing, and writes points in exactly
the payload format the CLI reads.

```bash
cd prompt_quill
.venv/bin/python scripts/index_prompts.py /path/to/your/prompts/
```

Useful flags: `--qdrant-url`, `--collection` (default `prompts_ng_gte`), `--vector-size`
(default 768). The embedding model is fixed to `BAAI/bge-base-en-v1.5` — the same one the
CLI uses, so no extra flag is needed at query time.

**Optional per-file metadata.** A file may start with header lines that become the point's
metadata and are *not* embedded:

```text
## negative: lowres, blurry, watermark, bad anatomy
## model: DreamShaper 8
a cinematic shot of a lighthouse in a storm at night, dramatic waves ...
```

`## negative:` feeds the `-n/--negative` output; `## model:` feeds the "Maybe helpful
models" list. Both are optional — plain prompt files work fine without them.

Re-running the script on the same files **updates** existing points (IDs are derived from
the file path) rather than duplicating them, so you can safely re-index after edits.

## Step 3 — verify end-to-end

1. The collection exists:
   ```bash
   curl http://localhost:6333/collections | python3 -m json.tool
   # look for "prompts_ng_gte" and a non-zero points_count
   ```
2. Run the CLI with `-n` so you can see RAG actually contributing (the negative prompt and
   model list only come from retrieved data):

   ```bash
   .venv/bin/prompt-quill -n "rocket man in space"
   ```

   No extra flags are needed — both paths index with the same fixed embedding model the CLI
   queries with. A working RAG setup prints a long enhanced prompt, then a `Maybe helpful negative
   prompt:` section and usually a `Maybe helpful models:` section. If you see the warning
   `warning: RAG unavailable (...)` on stderr instead, jump to Troubleshooting.

## Troubleshooting

- **`warning: RAG unavailable (ConnectionError: ...)`** — Qdrant isn't reachable at the URL
  the CLI uses (`http://localhost:6333` by default). Is the server running? Check with
  `curl http://localhost:6333/collections`. If you use a non-default location, pass
  `--qdrant-url` (or set `QDRANT_URL`).
- **No warning, but context looks irrelevant / negative prompt is just the default** — most
  likely an embedding-model mismatch. The CLI embeds queries with `BAAI/bge-base-en-v1.5`
  (fixed in code); if your collection was indexed with a different model, retrieval silently
  degrades. Re-index it with that model (Path B's helper does this automatically) or load the
  prebuilt dataset (Path A).
- **`port already in use`** — something else is on 6333/6334. Find it with
  `ss -ltnp | grep 6333`, stop it, or run Qdrant on another port and point the CLI at it
  via `--qdrant-url`.
- **Collection exists but has 0 points** — data didn't load (Path A) or the indexer found
  no non-empty files (Path B). Re-check Step 2.
- **I just want to skip RAG entirely** — use `--no-rag`; it skips retrieval and also avoids
  loading the embedding model, so calls are faster.

## Where things live / how to stop everything

| Item | Location |
|---|---|
| Docker server + data | container `qdrant`, volume `qdrant_storage` (`docker volume ls`) |
| Binary server + data | `~/qdrant/` (config in `config.yaml`, data in `storage/`) |
| Web UI | http://localhost:6334 |

Stopping the server does **not** delete your data — it's on disk. Restarting re-loads it.
