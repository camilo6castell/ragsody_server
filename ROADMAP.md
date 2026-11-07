# Roadmap

This roadmap covers planned work for the Ragsody document question-answering (RAG) backend. Estimates are engineering hours for a single developer and assume the current Python/FastAPI/FAISS codebase.

**Scope note:** This roadmap excludes training, fine-tuning, benchmarking, evaluation tooling, and model serving. The project is a document Q&A backend that routes generation to configured LLM runtimes.

## Planned work

| ID | Item | Description | Estimate (hours) |
|---:|---|---|---:|
| R1 | Secret-history remediation and branch hygiene | After the leaked historical archive is removed from all branches (developer-run git-filter-repo/BFG), rotate every exposed credential, verify cached GitHub views are purged, fast-forward the default branch to the current release state, and document the incident response. | 3.0 |
| R2 | REST API smoke and contract tests | Add FastAPI `TestClient` tests for `/health`, `/api/v1/collections`, `/api/v1/config/providers`, and `/api/v1/query` error paths using mocked providers and in-memory fixtures. No real LLM or external API calls. | 3.5 |
| R3 | MCP server smoke tests | Add tests for `list_collections`, `retrieve_chunks`, and `search_web` behavior with mocked retrieval/web dependencies and bearer-token validation. | 2.5 |
| R4 | Storage and ingestion integration tests | Add isolated tests for FAISS save/load/delete flows and ingestion chunk/metadata behavior using temporary `AI_HOME` directories. | 3.0 |
| R5 | Provider and fallback behavior tests | Cover role routing, fallback selection, empty-response fallback, and unsupported generation-option validation without network access. | 2.0 |
| R6 | Dependency and packaging cleanup | Reconcile `requirements.txt` and `pyproject.toml`, document the optional SentenceTransformer install path, and decide whether to add a supported build system or keep the in-place app layout explicit. | 2.0 |
| R7 | Third-party skill attribution cleanup | Remove unlicensed bundled skill files from the submission history/index or add explicit upstream source, license, and attribution for each retained skill. | 1.5 |
| R8 | Crawler safety and observability | Add a configurable user agent, `robots.txt` handling, request logging, and clearer operator controls for bounded crawling. | 2.0 |
| R9 | Operational hardening | Add startup checks for required role configuration, improve health/readiness reporting, and document safe deployment defaults for MCP/API exposure. | 1.5 |
| R10 | Documentation maintenance pass | Keep README, `.env` templates, API examples, and repository metadata aligned with the code whenever endpoints, defaults, or provider behavior change. | 1.0 |

**Total: 22.0 hours**

## Out of scope

- Model training or fine-tuning
- Benchmarking or evaluation tooling
- Model serving infrastructure
- Automated data acquisition beyond the existing bounded, operator-triggered ingestion/crawler flow
