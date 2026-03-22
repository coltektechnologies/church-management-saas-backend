# RAG & Agent — Documentation Index

This folder contains step-by-step guides to add **RAG** (Retrieval-Augmented Generation) and an **Agent** to your Church Management SaaS backend.

---

## What You Get

| Component | Purpose |
|-----------|--------|
| **RAG** | Answer questions using your church data and docs (e.g. policies, API usage, FAQs). |
| **Agent** | Perform actions via your APIs (e.g. list pending expense requests, department stats, create drafts). |

Both can run as a separate Python service that calls your existing Django REST API.

---

## Documentation Files (Root Folder)

| File | Description |
|------|-------------|
| **RAG_AND_AGENT_README.md** | This file — overview and index. |
| **RAG_SETUP_GUIDE.md** | Step-by-step RAG: embeddings, vector store, retrieval, LLM. |
| **AGENT_SETUP_GUIDE.md** | Step-by-step Agent: tools, LLM, calling your APIs. |
| **RAG_AND_AGENT_PREREQUISITES.md** | Accounts, APIs, env vars, and security checklist. |

---

## Your Existing API (What the Agent Can Use)

Base URL (example): `http://localhost:8000/api/` or your production URL.

| Area | Examples |
|------|----------|
| Auth | `POST /api/auth/login/`, JWT refresh |
| Members | `GET/POST /api/members/`, create, list |
| Departments | `GET/POST /api/departments/`, update, head, elder |
| Treasury | `GET/POST /api/treasury/expense-requests/`, disburse, transactions |
| Announcements | `GET/POST /api/announcements/`, categories, `new_within_days` |
| Notifications | `GET/POST /api/notifications/`, batches, recurring-schedules |
| Reports / Analytics | `GET /api/reports/`, `GET /api/analytics/` |

Full API docs: `/api/docs/` (Swagger) and `/api/redoc/` (ReDoc).

---

## Recommended Order

1. Read **RAG_AND_AGENT_PREREQUISITES.md**.
2. Follow **RAG_SETUP_GUIDE.md** for a first RAG pipeline.
3. Follow **AGENT_SETUP_GUIDE.md** to add an agent with API tools.
4. Optionally combine: Agent uses RAG for “knowledge” and tools for “actions”.

---

## Quick Prerequisites

- Python 3.10+
- LLM access (OpenAI, Anthropic, Azure, or local e.g. Ollama)
- Embedding model (same provider or dedicated)
- Vector store (Chroma, Pinecone, Weaviate, or pgvector)
- Your Django backend running and reachable (for the agent)
