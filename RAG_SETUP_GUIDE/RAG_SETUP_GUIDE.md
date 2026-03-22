# RAG Setup Guide — Step by Step

Build a **Retrieval-Augmented Generation (RAG)** pipeline that answers questions using your church management docs and data.

---

## Step 1: Create a Dedicated Directory (Optional)

```bash
mkdir -p rag_service
cd rag_service
python -m venv venv
source venv/bin/activate
```

---

## Step 2: Install Dependencies

```bash
pip install openai chromadb
```

For local LLM use `ollama` and `chromadb`. For LangChain: `langchain langchain-openai chromadb`.

---

## Step 3: Prepare Your Documents

- Export or write content (Markdown or plain text): API usage, approval flows, FAQs.
- Save under e.g. `rag_service/documents/`.

---

## Step 4: Chunk and Embed Documents

Create `rag_service/ingest.py`:

- Use Chroma with an embedding function (e.g. OpenAI `text-embedding-3-small`).
- Chunk each document (e.g. 500 chars, 50 overlap).
- Add chunks to a Chroma collection with `collection.add(documents=chunks, ids=ids)`.

Run once: `export OPENAI_API_KEY=... ; python ingest.py`.

---

## Step 5: Implement Retrieval + LLM (Query Pipeline)

Create `rag_service/query.py`:

1. **Retrieve**: Embed the user question, query the Chroma collection for top-k similar chunks.
2. **Prompt**: Build a prompt with "Context: ..." (retrieved chunks) and "Question: ...".
3. **Generate**: Call OpenAI (or your LLM) with that prompt and return the answer.

Example flow: `retrieve(question)` → `prompt = f"Context:\n{context}\n\nQuestion: {question}"` → `openai.chat.completions.create(...)`.

---

## Step 6: Expose as a Small API (Optional)

Use FastAPI: one endpoint `POST /ask` with body `{"question": "..."}` that calls your `ask(question)` from Step 5 and returns `{"answer": "..."}`. Run with `uvicorn main:app --port 8001`.

---

## Step 7: Integrate with Your Backend or Agent

- From Django: call the RAG service when a user asks a question.
- From the Agent: add a RAG tool that calls this service so the agent can use “knowledge” before acting.

---

## Summary Checklist

- [ ] Directory and venv
- [ ] Install LLM client + Chroma (or other vector store)
- [ ] Prepare documents
- [ ] Ingest: chunk → embed → store
- [ ] Query: retrieve → prompt LLM → return answer
- [ ] Optional: FastAPI wrapper and integration

Next: **AGENT_SETUP_GUIDE.md** for an agent that uses your church API as tools.
