# RAG & Agent — Prerequisites

Before starting the RAG and Agent setup guides, ensure the following are in place.

---

## 1. Python Environment

- **Python**: 3.10 or 3.11 recommended.
- **Virtual environment**: Use a dedicated venv for the RAG/Agent service (can live inside or outside this repo).

```bash
python -m venv venv_rag
source venv_rag/bin/activate   # Linux/macOS
# or: venv_rag\Scripts\activate  # Windows
```

---

## 2. LLM & Embeddings Access

Choose one path:

| Option | LLM | Embeddings | Notes |
|--------|-----|------------|--------|
| **OpenAI** | GPT-4 / 3.5 | text-embedding-3-small | Set `OPENAI_API_KEY` |
| **Anthropic** | Claude | Use OpenAI or another for embeddings | Set `ANTHROPIC_API_KEY` |
| **Azure OpenAI** | GPT via Azure | Embeddings via Azure | Set Azure endpoint + key |
| **Local (Ollama)** | Llama, Mistral, etc. | e.g. nomic-embed-text | No API key; runs on your machine |

You need at least:
- One **LLM** for generation (and for the agent’s reasoning).
- One **embedding model** for RAG (if you use RAG).

---

## 3. Vector Store (for RAG)

Pick one and have it reachable:

| Store | Use case | Setup |
|-------|----------|--------|
| **Chroma** | Simple, file-based | `pip install chromadb` |
| **pgvector** | Use existing Postgres | Extension in your DB |
| **Pinecone** | Managed, scalable | Account at pinecone.io |
| **Weaviate** | Self-hosted or cloud | Docker or Weaviate Cloud |

---

## 4. Church Management Backend (for the Agent)

- **Django backend** running (this repo).
- **Base URL** known, e.g. `http://localhost:8000` or `https://your-api.com`.
- **Authentication**: Agent will call your API with a valid token (e.g. JWT).
  - Create a **service user** or use an existing user.
  - Obtain access (and optionally refresh) token via `POST /api/auth/login/` (or your auth endpoint).
  - Store token in env (e.g. `CHURCH_API_TOKEN`) or fetch at startup; never commit tokens.

---

## 5. Environment Variables (Example)

Create a `.env` file (or set in the environment) for the RAG/Agent service. Do not commit secrets.

```env
# LLM (choose one provider)
OPENAI_API_KEY=sk-...
# OR ANTHROPIC_API_KEY=...
# OR AZURE_OPENAI_ENDPOINT=... and AZURE_OPENAI_KEY=...

# Backend API (for the agent)
CHURCH_API_BASE_URL=http://localhost:8000/api
CHURCH_API_EMAIL=agent@yourchurch.com
CHURCH_API_PASSWORD=...

# Optional: use a long-lived token instead of email/password
# CHURCH_API_TOKEN=eyJ...

# Vector store (if using Chroma, path; if using Pinecone/Weaviate, their env vars)
CHROMA_PERSIST_DIR=./chroma_data
```

---

## 6. Content for RAG (Optional but Recommended)

Gather text the RAG will search over, for example:

- API documentation (e.g. export from `/api/docs/` or ReDoc).
- Internal docs: approval flows, expense request process, department roles.
- FAQs or policy snippets.

Store them as plain text or Markdown; the RAG guide will show how to chunk and embed them.

---

## 7. Security Checklist

- [ ] No API keys or passwords in code or in git.
- [ ] Agent uses a dedicated service user with minimal required permissions.
- [ ] Backend API is over HTTPS in production.
- [ ] Vector store access (if cloud) restricted by key and network.
- [ ] Rate limits and quotas set for LLM and API usage.

Once these are in place, proceed to **RAG_SETUP_GUIDE.md** and **AGENT_SETUP_GUIDE.md**.
