# SentinelMCP — Multi‑Agent RAG with MCP & Compliance (Saptiva‑native)

## Overview
**SentinelMCP** is a production‑minded system for **Retrieval‑Augmented Generation (RAG)** with **multi‑agent orchestration** and **Model Context Protocol (MCP)** integration. It exposes institutional tools (CFDI/SAT verification, CURP lookup, OCR/parse of official docs) behind a compliant interface with **Human‑in‑the‑Loop (HITL)**, **auditable traces**, and **state persistence**.

This project is intentionally **Saptiva‑native**:
- **Reasoning & coordination** → `Saptiva Cortex` (planning/selection) and `Saptiva Ops` (tool‑calling & operations).
- **Embeddings** → `Saptiva Embed` for semantic indexing & retrieval.
- **Moderation/compliance** → `Saptiva Guard` for policy screening.
- **OCR/extraction** → `Saptiva OCR` + built‑in PDF extraction tools.
- **Agents runtime** → `saptiva‑agents` (selector teams, terminations, logging, state).

> Target domains: regulated **government**, **banking**, and **national security** workloads that require provenance, reproducibility, and controlled access to sensitive tools and data.

---

## Why SentinelMCP
- **MCP‑first integration.** Tools are exposed via MCP so IDEs, internal apps, and agent hosts can reuse them without bespoke SDKs.
- **Compliance by construction.** HITL checkpoints, structured logging, and model/tool scoping enforce separation of duties.
- **Saptiva alignment.** Uses Saptiva models and the `saptiva‑agents` runtime to reduce glue code and improve reliability.
- **Reproducibility.** Agent/team **state serialization** and **evidence packs** make every decision auditable.

---

## High‑Level Architecture

```mermaid
flowchart LR
  subgraph Client["Clients"]
    UI["Web UI / CLI"]
    MCPClients["MCP Clients (IDEs, internal apps)"]
  end

  subgraph Gateway["API Gateway (TLS, AuthN/Z)"]
    REST["/ask, /search, /ingest, /mcp"]
  end

  Client -->|HTTPS| Gateway

  subgraph Orchestrator["Multi-Agent Orchestrator (saptiva-agents)"]
    Sel["SelectorGroupChat (Cortex/Ops)"]
    Planner["PlanningAgent (Cortex)"]
    Retriever["RetrievalAgent (Embed)"]
    Analyst["AnalystAgent (Ops)"]
    Guard["GuardAgent (Saptiva Guard)"]
    HIL["UserProxyAgent (HITL)"]
  end

  Gateway --> Orchestrator
  Sel --> Planner
  Planner --> Retriever
  Retriever --> Index

  subgraph Index["Vector Index (pgvector/Chroma)"]
    Embeds["Embeddings: Saptiva Embed"]
    Docs["Chunks + metadata"]
  end

  Retriever -->|Top-k| Analyst
  Analyst --> Tools
  Tools --> Analyst
  Analyst --> Guard
  Guard -->|policy pass/fail| HIL
  HIL -->|approval| Gateway

  subgraph Tools["MCP + Custom Tools"]
    SAT["get_verify_sat / consultar_cfdi"]
    CURP["consultar_curp_*"]
    PDF["obtener_texto_en_documento (OCR/PDF)"]
    CSV["upload_csv (tabular)"]
    WIKI["wikipedia_search (open)"]
  end

  subgraph Observability["Observability & Audit"]
    Logs["Structured logs (EVENT_LOGGER_NAME)"]
    Trace["Trace logs (TRACE_LOGGER_NAME)"]
    Store["State persistence (dump/load)"]
  end

  Orchestrator --> Logs
  Orchestrator --> Trace
  Orchestrator --> Store
```

**Key ideas**
- **Selector‑based orchestration.** The selector chooses the next agent (Planner/Retriever/Analyst/Guard/HIL) based on context—not round‑robin.
- **HITL where it matters.** Use `UserProxyAgent` for approvals on sensitive actions and disclosures.
- **Explicit termination.** Terminate on text mentions/handoffs or max‑turns to avoid loops.
- **Persistent state.** Save/restore team state to resume long KYC/fraud investigations.

---

## Data Flow

### Ingestion
1. Upload documents (PDF/images/CSV) via `/ingest`.
2. Extract text using `obtener_texto_en_documento` (Saptiva OCR) → clean text + metadata.
3. Chunk into 1–2k token windows (sliding window for continuity).
4. Embed with **Saptiva Embed** and write to the vector index.

### Query
1. Planner reformulates the user question and sets retrieval constraints.
2. Retriever performs **semantic search** (MMR/top‑k + metadata filters).
3. Analyst composes the answer; when needed, calls MCP/Custom Tools (CFDI/SAT/CURP/PDF/CSV).
4. Guard validates against policies (moderation/compliance).
5. If a policy demands a human checkpoint, **HITL** approves; otherwise the answer is returned with citations.

---

## Core Components
- **API Gateway** — FastAPI/ASGI with `/ask`, `/search`, `/ingest`, `/mcp`, `/healthz`.
- **Orchestrator** — `saptiva‑agents` team: Selector, Planner (Cortex), Retriever (Embed), Analyst (Ops), Guard, HITL.
- **Vector Index** — pgvector or Chroma for embeddings & metadata.
- **MCP Tooling** — Slim MCP server exposing tools so agent hosts and IDEs can call them directly.
- **Observability** — Structured logs + traces; ready for SIEM/OTEL exporters.
- **State Store** — Persist agent/team state for replay and resumption.

---

## Saptiva‑Native Models (recommended)
- **Reasoning/Planning:** `Saptiva Cortex` for selection/planning and final grounded answers.
- **Tool‑use/Operations:** `Saptiva Ops` for structured tool calling and data‑heavy steps.
- **Embeddings:** `Saptiva Embed` for semantic indexing and retrieval.
- **Moderation/Compliance:** `Saptiva Guard` to enforce policies.
- **OCR/Extraction:** `Saptiva OCR` to parse scanned/official documents.

> The router chooses the right model per task to balance **latency**, **cost**, and **accuracy**. Default to Cortex for planning and final answers; switch to Ops when tool‑use is central to the step.

---

## Security, Compliance & Audit
- **Policy screening** with Saptiva Guard before emitting results or downloading files.
- **PII handling**: redact at log ingestion; hash PII fields; avoid storing raw documents unless retention is explicitly required.
- **Structured logging** with `EVENT_LOGGER_NAME` and **trace logging** with `TRACE_LOGGER_NAME` for every tool‑call and agent handoff.
- **State persistence**: serialize team/agent state per case (KYC/fraud) to enable replay, re‑audit, and safe resume after HITL.
- **Separation of duties**: only HITL‑approved transitions can escalate to high‑risk actions (e.g., filing a compliance alert).

> Note: access to official SAT/RENAPO endpoints typically requires authorized providers. This project ships a `MockProvider` for demos and a pluggable `ProviderInterface` for real integrations.

---

## Endpoints
- `POST /ingest` — Upload docs → OCR → chunk → embed → index.
- `POST /search` — Retrieve top‑k passages (no generation).
- `POST /ask` — RAG answer with citations, optional tool‑calls, Guard policy check, and optional HITL.
- `POST /mcp/call` — Invoke MCP‑exposed tools (CFDI, CURP, SAT, CSV, PDF).
- `GET /healthz` — Liveness probe.

---

## Environment Variables
```
SAPTIVA_API_KEY=...

SAPTIVA_MODEL_REASONS=Saptiva Cortex
SAPTIVA_MODEL_TOOLS=Saptiva Ops
SAPTIVA_MODEL_EMBED=Saptiva Embed
SAPTIVA_MODEL_GUARD=Saptiva Guard
SAPTIVA_MODEL_OCR=Saptiva OCR

VECTOR_DB_URL=postgres://user:pass@host:5432/db   # or local Chroma path
DOC_STORE_BUCKET=...                               # optional blob store
LOG_LEVEL=INFO
```

---

## Quickstart (dev)

1) **Install** (Python 3.10+):
```bash
pip install -U saptiva-agents fastapi uvicorn chromadb psycopg[binary] pydantic
```

2) **Run the API** (development):
```bash
export SAPTIVA_API_KEY=your_key_here
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3) **Ingest a PDF**:
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@./docs/policy.pdf" \
  -F "metadata={\"type\":\"policy\",\"jurisdiction\":\"MX\"}"
```

4) **Ask a question**:
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the identity requirements for supplier onboarding? Cite the policy.",
    "k": 5
  }' | jq
```

5) **Call an MCP tool** (example):
```bash
curl -s -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "consultar_cfdi",
    "params": {"url": "https://example.com/cfdi.xml"}
  }' | jq
```

---

## Observability
Enable structured logging and traces (OTEL‑friendly). Minimal example in `infra/logging.py`:
```python
import logging
from saptiva_agents.core import EVENT_LOGGER_NAME, TRACE_LOGGER_NAME

def enable_logs(level=logging.INFO):
    logging.basicConfig(level=level)
    logging.getLogger(EVENT_LOGGER_NAME).setLevel(logging.INFO)
    logging.getLogger(TRACE_LOGGER_NAME).setLevel(logging.DEBUG)
```
Exporters can forward logs to your SIEM/OTLP backends.

---

## Evaluation & Benchmarks
- **RAG quality**: has‑support (answer spans found), exactness of citations, groundedness score, top‑k recall.
- **Latency**: p50/p95 for retrieval, tool‑calls, and end‑to‑end answers.
- **Guard**: correct block/allow rates, FP/FN on policy rules.
- **HITL**: % of cases requiring human review, time‑to‑approval, human‑model agreement.
- **Cost**: tokens by step (planning, retrieval, answer, tools).

Include a **golden set** with anonymized CFDI/CURP cases and adversarial OCR samples.

---

## Repository Structure
```
sentinelmcp/
  ├─ app/
  │   ├─ main.py                # FastAPI routes (/ingest, /search, /ask, /mcp)
  │   └─ mcp_server.py          # MCP server (HTTP+SSE) exposing tools
  ├─ agents/
  │   ├─ orchestrator.py        # Selector/Planner/Retriever/Analyst/Guard/HIL wiring
  │   └─ tools_wrappers.py      # Adapters to Saptiva Custom Tools
  ├─ rag/
  │   ├─ ingest.py              # OCR + chunk + embed pipeline
  │   └─ retriever.py           # semantic search, filters
  ├─ infra/
  │   ├─ logging.py             # structured/trace logging helpers
  │   └─ state_store.py         # save/load team/agent state
  ├─ tests/
  │   ├─ test_ingest.py
  │   ├─ test_rag.py
  │   └─ test_tools.py
  └─ README.md
```

---

## Roadmap (suggested)
1. **MVP** — MCP server + `/ingest` + `/ask` with Cortex/Ops/Embed + basic Guard.
2. **HITL** — UserProxyAgent approvals; resumable state per case.
3. **Observability** — structured logs + traces; dashboards for p95 & cost.
4. **Providers** — `ProviderInterface` with `MockProvider` and real provider glue.
5. **Hardening** — rate‑limits, circuit breakers, retries with jitter, idempotency keys.
6. **Portability** — optional OpenAI‑compatible proxy tests for “no lock‑in” story.

---

## Risks & Mitigations
- **Third‑party availability (e.g., SAT)** → circuit breakers + cached last‑known status + HITL fallback.
- **Prompt injection / tool misuse** → Guard policy checks + tool whitelisting + strict system prompts.
- **PII exposure** → redaction at logs, encryption at rest, short retention windows.
- **Hallucinations** → require citations; block answers without evidence; fallback to HITL.

---

## License
TBD (MIT/Apache‑2.0 suggested for prototyping).

---

## Acknowledgments
This project aligns with the Saptiva documentation for agents, models, RAG, tools, logging, and state management. Replace the `MockProvider` with authorized providers for official CFDI/CURP verification in production deployments.
