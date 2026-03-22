# Agent Setup Guide — Step by Step

This guide walks you through building an **Agent** that uses your Church Management API as **tools** (e.g. list expense requests, get department stats, create drafts).

---

## Step 1: Create a Dedicated Directory

```bash
mkdir -p agent_service
cd agent_service
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
```

---

## Step 2: Install Dependencies

```bash
pip install openai requests
# If using LangChain for tools + agent:
# pip install langchain langchain-openai
```

---

## Step 3: Obtain API Access (Token)

The agent must call your Django API with a valid JWT (or your auth scheme).

**Option A — Login and store token:**

```python
# get_token.py
import os
import requests

BASE = os.environ["CHURCH_API_BASE_URL"]  # e.g. http://localhost:8000/api
email = os.environ["CHURCH_API_EMAIL"]
password = os.environ["CHURCH_API_PASSWORD"]
# If your login expects church_id, add it.
r = requests.post(f"{BASE.replace('/api', '')}/api/auth/login/", json={
    "email": email,
    "password": password,
})
r.raise_for_status()
token = r.json().get("access")  # or "access_token" per your API
print(token)
```

**Option B — Use a long-lived token** stored in `CHURCH_API_TOKEN` (if your backend supports it).

Set in env: `CHURCH_API_BASE_URL`, `CHURCH_API_EMAIL`, `CHURCH_API_PASSWORD` (or `CHURCH_API_TOKEN`).

---

## Step 4: Define Tools (API Calls)

Create `agent_service/tools.py`:

```python
import os
import requests

BASE = os.environ.get("CHURCH_API_BASE_URL", "http://localhost:8000/api").rstrip("/")

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def list_expense_requests(token, status=None):
    url = f"{BASE}/treasury/expense-requests/"
    if status:
        url += f"?status={status}"
    r = requests.get(url, headers=get_headers(token))
    r.raise_for_status()
    return r.json()

def get_departments(token):
    r = requests.get(f"{BASE}/departments/", headers=get_headers(token))
    r.raise_for_status()
    return r.json()

def get_department_detail(token, dept_id):
    r = requests.get(f"{BASE}/departments/{dept_id}/", headers=get_headers(token))
    r.raise_for_status()
    return r.json()

def get_treasury_statistics(token):
    r = requests.get(f"{BASE}/treasury/statistics/", headers=get_headers(token))
    r.raise_for_status()
    return r.json()
```

Add more tools as needed (e.g. list announcements, create draft, etc.) following the same pattern.

---

## Step 5: Describe Tools for the LLM

Create a list of tool definitions the LLM can choose from:

```python
# agent_service/tool_defs.py
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_expense_requests",
            "description": "List expense requests. Optionally filter by status: DRAFT, SUBMITTED, DEPT_HEAD_APPROVED, APPROVED, DISBURSED, REJECTED.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_departments",
            "description": "List all departments (id, name, code, etc.)."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_department_detail",
            "description": "Get one department by ID (member_count, heads, elder_in_charge, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "dept_id": {"type": "string", "description": "Department UUID"}
                },
                "required": ["dept_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_treasury_statistics",
            "description": "Get treasury summary: income, expenses, pending requests, assets."
        }
    },
]
```

---

## Step 6: Implement the Agent Loop

Create `agent_service/agent.py`:

```python
import os
import json
from openai import OpenAI
from get_token import get_token  # you implement: returns JWT
from tools import list_expense_requests, get_departments, get_department_detail, get_treasury_statistics
from tool_defs import TOOLS

client = OpenAI()
token = get_token()  # or os.environ["CHURCH_API_TOKEN"]

def run_tool(name, arguments):
    args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    if name == "list_expense_requests":
        return list_expense_requests(token, status=args.get("status"))
    if name == "get_departments":
        return get_departments(token)
    if name == "get_department_detail":
        return get_department_detail(token, args["dept_id"])
    if name == "get_treasury_statistics":
        return get_treasury_statistics(token)
    return {"error": f"Unknown tool: {name}"}

def run_agent(user_message, max_turns=5):
    messages = [
        {"role": "system", "content": "You are an assistant for a church management system. Use the provided tools to answer. Be concise."},
        {"role": "user", "content": user_message}
    ]
    for _ in range(max_turns):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        choice = response.choices[0]
        if not choice.message.tool_calls:
            return choice.message.content
        for tool_call in choice.message.tool_calls:
            name = tool_call.function.name
            args = tool_call.function.arguments
            result = run_tool(name, args)
            messages.append(choice.message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)[:4000]
            })
    return "Max turns reached."
```

Implement `get_token()` in `get_token.py` (login once and return `access` token, or read from env).

---

## Step 7: Run the Agent

```python
# main.py
from agent import run_agent
print(run_agent("How many expense requests are pending approval?"))
print(run_agent("List all departments and their member counts."))
```

Run: `python main.py`. Extend with more tools and better system prompts as needed.

---

## Step 8: Optional — Combine with RAG

- Add a RAG tool: “Search knowledge base for X” that calls your RAG service (`POST /ask` from RAG_SETUP_GUIDE).
- Agent can then both **query docs** (RAG) and **call your API** (tools) to answer and act.

---

## API Endpoints Reference (This Project)

Use these to add more tools:

| Area | Method | Endpoint (under /api/) |
|------|--------|-------------------------|
| Expense requests | GET/POST | treasury/expense-requests/ |
| Expense request detail | GET/PATCH | treasury/expense-requests/{id}/ |
| Submit / Approve / Disburse | POST | treasury/expense-requests/{id}/submit/ , .../approve-dept-head/ , .../disburse/ |
| Departments | GET/POST | departments/ |
| Department detail | GET/PATCH | departments/{id}/ |
| Department head | PUT | departments/{id}/head/ |
| Treasury stats | GET | treasury/statistics/ |
| Announcements | GET/POST | announcements/ |
| Notifications | GET/POST | notifications/notifications/ , notifications/batches/ |

Full list: open `/api/docs/` in your running Django app.

---

## Summary Checklist

- [ ] Step 1: Directory and venv
- [ ] Step 2: Install openai, requests
- [ ] Step 3: Get JWT (login or env token)
- [ ] Step 4: Implement tools (API wrappers)
- [ ] Step 5: Define tool schemas for the LLM
- [ ] Step 6: Agent loop: LLM → tool calls → run tools → LLM → final answer
- [ ] Step 7: Test with natural language questions
- [ ] Step 8: Optional RAG tool

You now have a working agent that can query and act on your church management API.
