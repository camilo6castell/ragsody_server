<div align="center">

<img src="https://img.shields.io/badge/Ragsody-RAG%20Multi--Context-0d1117?style=for-the-badge&logo=openai&logoColor=white" alt="Ragsody RAG" height="60"/>

# Ragsody [RAG Multi-Context] by Camilo Castellanos

**Document question-answering (RAG) backend. Multi-context retrieval. Multi-provider LLM routing.**

[![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FAISS](https://img.shields.io/badge/FAISS-IndexFlatIP-blue?style=flat-square)](https://github.com/facebookresearch/faiss)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-7C3AED?style=flat-square)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](./LICENSE)

</div>

---

## Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Multi-Provider LLM](#-multi-provider-llm)
- [Ingestion Pipeline](#-ingestion-pipeline)
- [Query Modes](#-query-modes)
- [REST API](#-rest-api)
- [MCP Server](#-mcp-server)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Related Repositories](#-related-repositories)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Security Notes](#-security-notes)
- [Contributing](#-contributing)
- [License](#-license)

---

## Overview

Ragsody is a **document question-answering (RAG) backend** designed as a personal semantic memory system. It lets you ingest your own documents and query multiple independent knowledge domains — psychoanalysis, philosophy, technical documentation, sociology, etc. — through a linear retrieval pipeline, a REST API, or an MCP server for AI-client integration.

**Core design principles:**

**Isolation** — each knowledge domain lives in its own FAISS index. Contexts never bleed into each other.

**Control** — every component of the pipeline (chunking, embedding, retrieval, generation) is explicit and tunable. No black-box abstractions.

**Provider choice** — each role can use a local runtime or an external provider. When a role is pointed at an external provider, the prompt for that role leaves the machine; the README documents that boundary instead of claiming a blanket privacy guarantee.

**Honesty** — the LLM is constrained by the prompt to answer only from retrieved context. When the answer is not in the documents, it says so.

**Production services:**
- **MCP server** — Streamable HTTP endpoint exposing retrieval and web-search tools (`list_collections`, `retrieve_chunks`, `search_web`) for any MCP-compatible client (Claude Desktop, OpenCode, etc.).
- **REST API** — FastAPI server with a linear RAG query endpoint, file upload, provider config, and a streaming demo endpoint.

---

## Architecture

```
                    ┌──────────────────────┐
                    │   User / AI Client    │
                    └──┬──────────────┬─────┘
                       │              │
          ┌────────────▼──┐    ┌──────▼────────────┐
          │  REST API     │    │  MCP Server        │
          │  FastAPI      │    │  Streamable HTTP    │
          │  /query       │    │  list_collections   │
          │  /demo/query  │    │  retrieve_chunks    │
          │  /collections │    │                     │
          └────────┬──────┘    └─────────┬───────────┘
                   │                     │
          ┌────────▼─────────────────────▼──────────┐
          │            Retrieval (FAISS)             │
          │  search(), format_context_chunks()       │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │            LLM Providers                 │
          │  Multi-role: generate, supplement        │
          │  Local backends: FLM, Ollama             │
          │  External: Gemini                         │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │         External Backends                │
          │  FastFlowLM / Ollama / Gemini API        │
          └─────────────────────────────────────────┘
```

### Filesystem layout

```
~/Documents/ragsody_data/
├── vector_stores/
│   ├── psicoanalisis/
│   │   └── Sigmund-Freud_La-interpretacion-de-los-suenos/
│   │       ├── index.faiss      # FAISS IndexFlatIP
│   │       ├── metadata.pkl     # ChunkMetadata list per chunk
│   │       └── vectors.npy      # raw embeddings for re-ranking
│   ├── sociologia/
│   │   └── ...
│   └── <category>/<collection>/
└── data/
    └── <files to ingest: PDF, HTML, TXT>
```

Collections are fully independent. Loading one never affects another, and multiple collections can be active simultaneously.

---

## Multi-Provider LLM

The system uses a **provider-per-role** architecture (`src/nlp/llm/providers.py`). Each role can use a different backend + model without any pipeline changes. Backends and per-role model choices are configured in `.env.providers` and resolved at runtime from a cached factory.

### Two independent axes

- **Backend** — a concrete runtime: `flm` (FastFlowLM) | `ollama` | `gemini`. Configured once with its URL (and credential, for Gemini):

  ```bash
  LLM_FLM_URL=http://127.0.0.1:52625/v1
  LLM_OLLAMA_URL=http://127.0.0.1:11434
  LLM_GEMINI_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  GEMINI_API_KEY=...
  ```

- **Role** — picks a `backend,model` pair directly:

  ```bash
  LLM_ROL_GENERATE=ollama,qwen3.5:4b
  LLM_ROL_SUPPLEMENT=ollama,qwen3.5:4b
  ```

Roles sharing the same `backend,model` share a single cached client instead of opening a duplicate connection.

### Fallback per role

Each role can also define an **optional fallback** (`LLM_ROL_*_FALLBACK`, same `backend,model` format). When configured, the pipeline retries the call on the fallback if the primary **errors or returns an empty response** — e.g. a cloud model with a local model as backup, so queries keep working when the external provider is unavailable or rate-limits:

```bash
LLM_ROL_GENERATE=gemini,gemini-2.5-flash-lite
LLM_ROL_SUPPLEMENT=gemini,gemini-2.5-flash-lite
LLM_ROL_GENERATE_FALLBACK=ollama,qwen3.5:4b
LLM_ROL_SUPPLEMENT_FALLBACK=ollama,qwen3.5:4b
```

Empty or absent `LLM_ROL_*_FALLBACK` = no fallback for that role (current behavior, error/empty response propagates as before). The fallback retry drops the primary's `think_mode` override, since the fallback model may not support it. The streaming demo endpoint (`/demo/query`) always uses the primary provider — streaming cannot be transparently retried on another backend.

### Provider privacy notes

Only roles pointed at a local backend (`flm`/`ollama`) keep the retrieved document chunks on the machine. Pointing a role at an external provider (Gemini) means that the prompt text for that specific task leaves the machine. This is a per-role choice, not a blanket privacy guarantee; review the routing in `.env.providers` before ingesting sensitive material.

### Adding a model to an existing backend

One entry in `src/config/models/<backend>.py` (`flm.py` | `ollama.py` | `gemini.py`) with its capabilities (`max_tokens`, `think_mode`, context window). No new environment variable needed.

### Adding a new backend

One entry in the registries at the top of `src/nlp/llm/providers.py` (`_backend_url_table`, `_backend_api_key_table`, `_BACKEND_CLIENT`), plus a new file in `src/config/models/` and, if it needs a distinct HTTP client, one in `src/nlp/llm/backends/`. Then point any role at it in `.env.providers`.

---

## Ingestion Pipeline

All ingestion modes share the same pipeline: **extract → chunk → embed → normalize → index → persist**.

```
Source (file / URL / domain)
         │
         ▼
  Text extraction
  (pypdf / BeautifulSoup4 / readability-lxml)
         │
         ▼
  chunk_text(text)
  ├── chunk_size:    500 chars
  └── chunk_overlap: 100 chars  (sliding window)
         │
         ▼
  get_encoder().encode(chunks)   ← pluggable (Ollama / FLM / SentenceTransformer)
  numpy float32 cast
  faiss.normalize_L2(embeddings) ← inner product → cosine similarity
         │
         ▼
  Append to existing index       ← always incremental, never rebuilds
  Update vectors.npy
  Update metadata.pkl
  Write index.faiss
```

### Ingestion modes

| Command                         | Source                       | Use case                  |
| ------------------------------- | ---------------------------- | ------------------------- |
| `ingest <cat> <col>`            | Local files (PDF, HTML, TXT) | Books, exported docs      |
| `ingest-url <cat> <col> <url>`  | Single URL                   | Articles, reference pages |
| `crawl <cat> <col> <start_url>` | Full domain (max 50 pages)   | Docs sites, wikis         |

All modes skip already-indexed sources via `existing_sources` deduplication — safe to re-run.

---

## Query Modes

Toggle with `/mode` in the CLI or via the `mode` field in the REST API.

|                 | HARD                                 | SOFT                                        |
| --------------- | ------------------------------------ | ------------------------------------------- |
| Top-K initial   | 15                                   | 25                                          |
| Top-K final     | 5                                    | 7                                           |
| LLM temperature | 0.0                                  | 0.0                                         |
| Prompt rules    | Strict: cite or say "not in context" | Flexible: synthesize, connect, abstract     |
| Best for        | Factual lookup, precise references   | Conceptual analysis, cross-source synthesis |

---

## REST API

A FastAPI server exposes the linear RAG pipeline as a REST endpoint.

```bash
python -m src.main api
# Listening on http://127.0.0.1:8000
```

### `POST /api/v1/query`

Linear RAG pipeline: retrieve → generate. No adaptive retrieval, prioritizes speed.

```json
{
  "question": "How does Freud describe the function of censorship in dreams?",
  "mode": "SOFT",
  "collections": [
    "psicoanalisis/Sigmund-Freud_La-interpretacion-de-los-suenos"
  ],
  "chat_history": []
}
```

Response:

```json
{
  "answer": "...",
  "confidence": 0.8021,
  "collections_used": ["psicoanalisis/Sigmund-Freud_La-interpretacion-de-los-suenos"],
  "used_web_search": false,
  "web_sources": null,
  "web_search_quota_exceeded": false
}
```

### `POST /api/v1/demo/query`

Streaming demo endpoint (SSE). Retrieves context, builds a prompt, and streams the LLM response token by token. Limited to 1 concurrent request.

```bash
curl -N -X POST http://127.0.0.1:8000/api/v1/demo/query \
  -H "Content-Type: application/json" \
  -d '{"question": "...", "collections": ["filosofia/Nietzsche"], "mode": "HARD"}'
```

### `GET /api/v1/collections`

Lists all available collections from the vectorstore directory.

### `POST /api/v1/files`

Upload a file (`.pdf`, `.html`, `.txt`) for ephemeral use in a conversation or attach it to a persisted collection. Multipart form fields: `conversation_id` (required), `attach_to_collection` (`true`/`false`), `collection` (required when attaching, format `namespace/collection`, e.g. `books/novels`).

- `attach_to_collection=false` (default) — processed with the same chunk/embed pipeline but kept **in memory only**, scoped to the conversation (see `src/context/ephemeral.py`).
- `attach_to_collection=true` — persists the result to disk in `collection`, exactly as if the ingest CLI had run it. Re-uploading a file already indexed in that collection returns `409` (same dedup as `ingest`).

### `GET /api/v1/files/{conversation_id}`

List ephemeral files for a conversation.

### `DELETE /api/v1/files/{conversation_id}/{file_id}`

Delete a single ephemeral file.

### `DELETE /api/v1/files/{conversation_id}`

Delete all ephemeral files for a conversation.

### `POST /api/v1/attachments`

Upload a plain-text file (up to 500 KB, UTF-8) to be injected **raw** into the prompt of the conversation's next query — never chunked or embedded. Multipart form field: `conversation_id`. Returns `400`/`413` on unsupported format or oversized file.

### `GET /api/v1/attachments/{conversation_id}`

List pending attachments for a conversation.

### `DELETE /api/v1/attachments/{conversation_id}/{file_id}`

Delete a single pending attachment.

### `DELETE /api/v1/attachments/{conversation_id}`

Delete all pending attachments for a conversation.

Attachments are **single-use**: once `/query` processes a message that included them, they are consumed (deleted) server-side and the list comes back empty — see `src/context/attachments.py`.

### `GET /api/v1/config/providers`

List provider capabilities (supports, default_think).

---

## MCP Server

A Streamable HTTP MCP server exposes retrieval tools for AI clients.

```bash
python -m src.main mcp
# Listening on http://127.0.0.1:8100
```

### Tools

| Tool                | Description                                       |
| ------------------- | ------------------------------------------------- |
| `list_collections`  | Lists all available vectorstore collections       |
| `retrieve_chunks`   | Searches collections and returns relevant chunks  |
| `search_web`        | Searches the web through Tavily when enabled      |

### Authentication

If `MCP_BEARER_TOKEN` is set, all requests must include an `Authorization: Bearer <token>` header. If empty (default), auth is disabled.

---

## Tech Stack

| Component            | Technology                                            |
| -------------------- | ----------------------------------------------------- |
| Language             | Python 3.11                                           |
| Embedding model      | Pluggable: Ollama (`bge-m3`), FLM, or SentenceTransformer |
| Vector index         | FAISS `IndexFlatIP` (exact cosine similarity)         |
| Vector normalization | L2 via `faiss.normalize_L2`                           |
| Local LLM runtime    | Any OpenAI-compatible endpoint (FastFlowLM, Ollama)   |
| External provider    | Gemini via OpenAI-compatible API                      |
| LLM backends         | `openai_compat`, `ollama_native`                      |
| REST API             | FastAPI + Uvicorn                                     |
| MCP Server           | Streamable HTTP (MCP SDK v2)                          |
| Configuration        | Pydantic Settings + `.env` files                      |
| PDF parsing          | pypdf                                                 |
| HTML extraction      | BeautifulSoup4 + readability-lxml                     |
| Numerical ops        | NumPy                                                 |
| Persistence          | `.faiss` + `.pkl` + `.npy` (no database required)     |
| Web search           | Tavily API (optional)                                 |
| Token validation     | tiktoken + context guard                              |

---

## Project Structure

```
.
├── .env                      # base config (never commit)
├── .env.providers            # LLM provider keys and routing (never commit)
├── .env.example              # base-config template — copy to .env
├── .env.providers.example    # provider-routing template — copy to .env.providers
├── requirements.txt
└── src/
    ├── main.py                # unified entry point (chat / api / mcp / server / ingest / crawl)
    ├── domain/
    │   └── models.py          # TurnMemory, ChatMode, LLMRole (shared types)
    ├── storage/
    │   └── faiss_store.py     # FAISS persistence (load/save/rebuild/vacuum/delete)
    ├── api/
    │   ├── app.py             # FastAPI application + lifespan
    │   ├── deps.py            # dependency injection (stores, managers)
    │   ├── routers/
    │   │   ├── chat.py        # /query, /collections
    │   │   ├── config.py      # /config/providers
    │   │   ├── demo.py        # /demo/query (streaming SSE)
    │   │   ├── files.py       # /files (ephemeral upload)
    │   │   └── attachments.py # /attachments
    │   └── schemas/           # Pydantic request/response models
    ├── cli/
    │   ├── interface.py       # interactive CLI loop
    │   ├── session.py         # session state (mode, memory, collections)
    │   ├── commands.py        # menu rendering and CLI helpers
    │   ├── modes.py           # re-exports ChatMode from domain
    │   └── types.py           # re-exports TurnMemory from domain
    ├── config/
    │   ├── settings.py        # Pydantic BaseSettings — all config in one place
    │   └── models/            # per-backend model capabilities (flm, ollama, gemini)
    ├── context/
    │   ├── manager.py         # load/unload collections from vectorstore
    │   ├── models.py          # SearchResult type
    │   ├── selector.py        # pattern matching for collection names
    │   ├── delete.py          # delete sources, URLs, clear collections
    │   ├── ephemeral.py       # in-memory file store for API conversations
    │   └── attachments.py     # persistent file attachments
    ├── mcp_server/
    │   └── server.py          # Streamable HTTP MCP server
    ├── ingest/
    │   ├── core.py            # chunk_text, encode_chunks, build_metadata
    │   ├── ingest.py          # local file ingestion (PDF / HTML / TXT)
    │   ├── web_ingest.py      # single URL ingestion
    │   ├── web_crawler.py     # domain crawler (up to MAX_PAGES)
    │   └── http.py            # shared URL content extraction (readability)
    ├── nlp/
    │   ├── embedders/
    │   │   └── encoder.py     # pluggable embedder (Ollama / FLM / SentenceTransformer)
    │   └── llm/
    │       ├── generate.py    # ask_llm / ask_llm_internal / build_messages
    │       ├── providers.py   # provider registry + cached client factory
    │       ├── roles.py       # re-exports LLMRole from domain
    │       ├── context_guard.py # token estimation + context window validation
    │       └── backends/
    │           ├── base.py           # LLMClient protocol
    │           ├── openai_compat.py  # OpenAI-compatible client (FLM, Gemini)
    │           └── ollama_native.py  # native Ollama client
    ├── prompts/
    │   └── builder.py         # prompt construction (system and web supplement)
    ├── retrieval/
    │   └── search.py          # FAISS search + cosine re-ranking
    └── utils/
        ├── logger.py
        └── tokens.py          # token estimation (tiktoken + heuristic fallback)
```

---

## Related Repositories

- **Client:** [camilo6castell/ragsody_client](https://github.com/camilo6castell/ragsody_client) — React/TypeScript client for the REST API and MCP server.
- **Live demo:** [ragsody.vercel.app](https://ragsody.vercel.app)

The backend and client are separate projects with independent model configuration. The client repository is required for the browser UI; this repository can run the API, MCP server, CLI, and ingestion pipeline on its own.

---

## Getting Started

### Prerequisites

- Python 3.11+
- A local LLM runtime ([FastFlowLM](https://fastflowlm.com/), [Ollama](https://ollama.com/), or similar)
- A Gemini API key for whichever roles you point at `gemini` in `.env.providers` (free tier sufficient)

### Install

```bash
git clone https://github.com/camilo6castell/ragsody_server.git
cd ragsody_server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Development tools (tests, lint, type checks)
pip install pytest ruff mypy

# Optional: in-process SentenceTransformer embedder.
# The default requirements target the Ollama and FLM HTTP backends.
# pip install sentence-transformers torch
```

### Configure environment and providers

```bash
cp .env.example .env
cp .env.providers.example .env.providers
```

`.env` contains base settings (chunking, retrieval, MCP, API, demo).
`.env.providers` contains backend URLs, credentials, and per-role model
routing. Both real files are gitignored; never commit them.

Edit `.env.providers`:

```env
# Backend URLs (configured once)
LLM_FLM_URL=http://127.0.0.1:52625/v1
LLM_OLLAMA_URL=http://127.0.0.1:11434
LLM_GEMINI_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_API_KEY=your_key_here

EMBEDDER_FLM_URL=http://127.0.0.1:52625/v1
EMBEDDER_OLLAMA_URL=http://127.0.0.1:11434

# Embedder: backend,model
EMBEDDER=ollama,bge-m3

# LLM per role: backend,model
LLM_ROL_GENERATE=gemini,gemini-2.5-flash-lite
LLM_ROL_SUPPLEMENT=gemini,gemini-2.5-flash-lite

# Optional fallback per role (used if the primary errors / returns empty)
LLM_ROL_GENERATE_FALLBACK=ollama,qwen3.5:4b
LLM_ROL_SUPPLEMENT_FALLBACK=ollama,qwen3.5:4b
```

### Create data and vector-store directories

```bash
# Default AI_HOME; set AI_HOME in .env to use another location.
mkdir -p "$HOME/Documents/ragsody_data/vector_stores"
mkdir -p "$HOME/Documents/ragsody_data/data"
```

---

## Usage

### Ingest

```bash
# Local files (place PDFs/HTML/TXT in ~/Documents/ragsody_data/data/ first)
python -m src.main ingest psicoanalisis Sigmund-Freud_La-interpretacion-de-los-suenos

# Single URL
python -m src.main ingest-url sociologia debord-espectaculo https://example.com/article

# Full domain crawl (up to MAX_PAGES pages)
python -m src.main crawl react hooks https://react.dev/learn
```

### Chat (CLI)

```bash
python -m src.main chat
```

**CLI commands:**

| Command             | Action                                                |
| ------------------- | ----------------------------------------------------- |
| `/context <tokens>` | Load one or more collections (space-separated tokens) |
| `/remove <tokens>`  | Unload one or more collections                        |
| `/list`             | List all available collections                        |
| `/active`           | Show active collections                               |
| `/clear`            | Unload all collections                                |
| `/mode`             | Toggle HARD / SOFT mode                               |
| `/reset`            | Clear conversation memory                             |
| `/help`             | Show all commands                                     |
| `/exit` or `/bye`   | Exit                                                  |

**Example session:**

```
> /context psicoanalisis
  + psicoanalisis/Sigmund-Freud_La-interpretacion-de-los-suenos

[ Sigmund-Freud_La-interpretacion-de-los-suenos | SOFT ]
> How does Freud describe the function of censorship in dreams?
```

### REST API

```bash
python -m src.main api
# → http://127.0.0.1:8000
# → Swagger UI: http://127.0.0.1:8000/docs
```

### MCP Server

```bash
python -m src.main mcp
# → http://127.0.0.1:8100
```

### API + MCP in one process

```bash
python -m src.main server
# → REST API: http://127.0.0.1:8000
# → MCP: http://127.0.0.1:8000/mcp/
```

This is the recommended mode for the browser client: it serves both the
REST endpoints and the mounted MCP server from one process.

### Interactive menu

```bash
python -m src.main
```

---

## Configuration

All configuration is managed via Pydantic Settings (`src/config/settings.py`) and loaded from `.env` + `.env.providers`.

| Variable               | Default                                                    | Description                                        |
| ---------------------- | ---------------------------------------------------------- | -------------------------------------------------- |
| `AI_HOME`              | `~/Documents/ragsody_data`                                 | Root directory for `vector_stores/` and `data/`    |
| `EMBEDDER`             | `ollama,bge-m3`                                            | `backend,model` used to generate embeddings        |
| `CHUNK_SIZE`           | `500`                                                      | Characters per chunk                               |
| `CHUNK_OVERLAP`        | `100`                                                      | Overlap between consecutive chunks                 |
| `MAX_PAGES`            | `50`                                                       | Max pages per web crawl                            |
| `HARD_TOP_K_INITIAL`   | `15`                                                       | FAISS candidates in HARD mode                      |
| `HARD_TOP_K_FINAL`     | `5`                                                        | Chunks passed to prompt in HARD mode               |
| `SOFT_TOP_K_INITIAL`   | `25`                                                       | FAISS candidates in SOFT mode                      |
| `SOFT_TOP_K_FINAL`     | `7`                                                        | Chunks passed to prompt in SOFT mode               |
| `MAX_TURNS`            | `4`                                                        | Conversation turns kept in context window          |
| `LLM_TIMEOUT`          | `600`                                                      | LLM call timeout in seconds                        |
| `LLM_FLM_URL`          | `http://127.0.0.1:52625/v1`                                | FastFlowLM endpoint                                |
| `LLM_OLLAMA_URL`       | `http://127.0.0.1:11434`                                   | Ollama endpoint                                    |
| `LLM_GEMINI_URL`       | `https://generativelanguage.googleapis.com/v1beta/openai/` | Gemini OpenAI-compatible endpoint                  |
| `GEMINI_API_KEY`       | —                                                           | Gemini API key                                     |
| `LLM_ROL_GENERATE`     | —                                                           | `backend,model` for answer generation              |
| `LLM_ROL_SUPPLEMENT`   | —                                                           | `backend,model` for the web-supplement decision    |
| `LLM_ROL_GENERATE_FALLBACK` | —                                                     | Optional `backend,model` fallback for generation   |
| `LLM_ROL_SUPPLEMENT_FALLBACK` | —                                                  | Optional `backend,model` fallback for supplement   |
| `EMBEDDER_FLM_URL`     | —                                                           | FLM embedding endpoint                             |
| `EMBEDDER_OLLAMA_URL`  | —                                                           | Ollama embedding endpoint                          |
| `WEB_SEARCH_ENABLED`   | `False`                                                     | Enable Tavily web search                           |
| `TAVILY_API_KEY`       | —                                                           | Tavily API key                                     |
| `API_HOST`             | `127.0.0.1`                                                | FastAPI bind address                               |
| `API_PORT`             | `8000`                                                     | FastAPI port                                       |
| `MCP_HOST`             | `127.0.0.1`                                                | MCP server bind address                            |
| `MCP_PORT`             | `8100`                                                     | MCP server port                                    |
| `MCP_BEARER_TOKEN`     | —                                                           | MCP server bearer token (empty = no auth)          |
| `MCP_ALLOWED_HOSTS`    | `127.0.0.1,localhost`                                       | Allowed Host headers for DNS-rebinding protection  |
| `MCP_LAN_HOST`         | —                                                           | Optional LAN/Tailscale host for MCP access         |

---

## Security Notes

- **`.env`, `.env.providers`, and `.env.*` files are gitignored** (except `.env.example` and `.env.providers.example`). Never commit API keys.
- Any role pointed at a local backend (`flm`/`ollama`) receives full document chunks in every request. Ensure your local runtime is not exposed on a public interface (`LLM_FLM_URL`/`LLM_OLLAMA_URL` should always bind to `127.0.0.1`).
- If `MCP_BEARER_TOKEN` is empty, MCP authentication is disabled. Set a token before exposing the MCP endpoint beyond localhost, and restrict `MCP_ALLOWED_HOSTS`/`MCP_LAN_HOST` to the interfaces you actually use.
- The FastAPI server also defaults to `127.0.0.1`. Do not expose it publicly without authentication and TLS.

---

## Quality checks

```bash
ruff check .
ruff format --check .
mypy .
pytest -q
```

`pytest` runs from a clean checkout without requiring real LLM credentials
because `tests/conftest.py` sets safe dummy provider roles.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request.

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit using [Conventional Commits](https://www.conventionalcommits.org/): `git commit -m 'feat: add your feature'`
4. Push and open a pull request

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

Copyright © 2026 Camilo Andrés Castellanos Herrera

---

<div align="center">

_Your documents. Your context. Your rules._

</div>
