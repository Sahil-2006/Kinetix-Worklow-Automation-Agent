# Kinetix — AI Workflow Automation Agent

> 🚀 **Track 5 Hackathon Entry** — Enterprise-grade workflow automation powered by LLM reasoning.

Turn natural-language requests into traceable workflows, with external actions simulated by default.

![Architecture](docs/architecture-flow.png)

---

## What It Does

Kinetix is an **agentic AI system** that uses the **ReAct (Reason → Act → Observe)** pattern to execute multi-step workflows from a single natural language command.

**Example:** *"Analyze sales.csv and email the top trends to ops@example.com"*

The agent will:
1. **Reason** — understand the request and plan tool calls
2. **Act** — call the CSV analyzer tool to find trends
3. **Observe** — read the analysis results
4. **Act** — compose and send an email with the findings
5. **Answer** — summarize what was done

All steps are streamed to the frontend in real time via **Server-Sent Events (SSE)**.

---

## Architecture

```
┌─────────────────┐    SSE     ┌──────────────────┐   HTTP   ┌───────────────┐
│  React Chat UI  │ ◄────────► │  FastAPI Backend  │ ──────► │  OpenRouter    │
│  (Vite + React) │            │  (ReAct Loop)     │         │  (LLM API)    │
└─────────────────┘            └──────────────────┘         └───────────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │  Tool Registry    │
                              ├──────────────────┤
                              │ CSV Analyzer      │
                              │ Google Calendar   │
                              │ SendGrid Email    │
                              │ File Read/Write   │
                              │ Report Summarizer │
                              │ Web Search        │
                              └──────────────────┘
```

### Security Model
- LLM receives the user prompt and workflow data needed to reason; API keys stay server-side
- All tool execution happens on the **backend**
- API keys are loaded from environment variables
- Email bodies and calendar attendee lists in action records are encrypted at rest; account email addresses remain plaintext in PostgreSQL
- File tools are restricted to the configured data folder, including protection against path traversal and escaping symlinks
- Prompts and selected file contents are sent to OpenRouter for reasoning; do not submit sensitive data without reviewing provider terms
- Real email and calendar actions stay disabled unless ENABLE_LIVE_ACTIONS=true

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite |
| Backend | FastAPI + Python 3.11+ |
| LLM | OpenRouter (Claude Sonnet 4) |
| Streaming | Server-Sent Events (SSE) |
| Database | Supabase (Postgres) |
| Queue | Redis + RQ |
| Email | SendGrid (simulated by default; live actions are opt-in) |
| Calendar | Google Calendar API (simulated by default; live actions are opt-in) |

---

## Quick Start

### 1. Backend

```bash
cd backend
cp .env.example .env
# Edit .env and add OPENROUTER_API_KEY, DATABASE_URL, and PII_ENCRYPTION_KEY
# Generate a Fernet key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and start chatting!

The included example data is under backend/data. Relative paths entered into
file or CSV tools are resolved from the configured AGENT_DATA_DIR. By default,
tools can read only text files up to 2 MiB, analyze CSV files up to 10 MiB, and
write files up to 100 KiB inside that folder.

Email and calendar actions are simulated even if provider credentials exist.
To enable external actions intentionally, set ENABLE_LIVE_ACTIONS=true and
configure the matching provider credentials. Review the workflow before
enabling this on any shared or deployed environment.

### 3. Background Worker (optional)

If you set `REDIS_URL`, start the RQ worker in another terminal:

```bash
cd backend
rq worker kinetix
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | **Yes** | Your OpenRouter API key |
| `OPENROUTER_MODEL` | No | LLM model (default: `anthropic/claude-sonnet-4`) |
| `DATABASE_URL` | **Yes** | Postgres connection string (Supabase) |
| `SENDGRID_API_KEY` | No | SendGrid key (falls back to mock) |
| `SENDGRID_FROM_EMAIL` | No | Sender email for SendGrid |
| `GOOGLE_CALENDAR_CREDENTIALS` | No | Base64 service account JSON (falls back to mock) |
| `GOOGLE_CALENDAR_ID` | No | Calendar ID (default: `primary`) |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID for Google sign-in |
| `MAX_REACT_ITERATIONS` | No | Max ReAct loop steps (default: `10`) |
| `PII_ENCRYPTION_KEY` | **Yes** | Fernet key for encrypting PII at rest |
| `REDIS_URL` | No | Redis connection URL for RQ workers |

---

## Available Tools

| Tool | Description | Mode |
|------|-------------|------|
| `csv_analyzer` | Analyze CSV files — stats, top values, trend detection | Real |
| `calendar_schedule` | Create Google Calendar events | Real / Mock |
| `email_send` | Send emails via SendGrid | Real / Mock |
| `file_read` | Read local text files | Real |
| `file_write` | Write content to local files | Real |
| `report_summarizer` | Summarize text into bullet points | Real |
| `web_search` | Search the web for information | Mock |

---

## Frontend Environment Variables

Create `frontend/.env` (or copy `frontend/.env.example`):

```bash
VITE_API_BASE=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-google-oauth-client-id
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check + tool list |
| `POST` | `/api/chat` | **Primary** — SSE streaming chat |
| `GET` | `/api/tools` | List registered tools |
| `POST` | `/api/command` | Legacy synchronous execution |
| `GET` | `/api/runs` | Run history |
| `GET` | `/api/runs/{id}` | Run details with steps |

---

## Project Structure

```
Kinetix-Worklow-Automation-Agent/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── orchestrator.py    # ReAct loop engine
│   │   │   ├── planner.py         # Legacy keyword planner (fallback)
│   │   │   └── prompts.py         # LLM system prompt
│   │   ├── core/
│   │   │   ├── config.py          # Environment configuration
│   │   │   └── llm_client.py      # OpenRouter async client
│   │   ├── security/
│   │   │   └── pii.py             # PII encryption + redaction
│   │   ├── storage/
│   │   │   └── db.py              # Postgres (Supabase) trace store
│   │   ├── queue.py               # RQ queue helpers
│   │   ├── workers/
│   │   │   └── tasks.py           # RQ background jobs
│   │   ├── tools/
│   │   │   ├── base.py            # Tool base class + schema
│   │   │   ├── csv_analyzer.py    # CSV analysis with trends
│   │   │   ├── calendar.py        # Google Calendar + mock
│   │   │   ├── email.py           # SendGrid + mock
│   │   │   ├── file_tools.py      # File read/write
│   │   │   ├── report_summarizer.py
│   │   │   └── web_search.py      # Web search (mock)
│   │   ├── executor.py            # Legacy step executor
│   │   ├── main.py                # FastAPI app + endpoints
│   │   ├── registry.py            # Tool registry
│   │   └── schemas.py             # Pydantic models
│   ├── data/                      # Sample data files
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatMessage.jsx    # Message bubbles
│   │   │   ├── ChatInput.jsx      # Input area
│   │   │   └── TracePanel.jsx     # Real-time trace viewer
│   │   ├── App.jsx                # Main chat + trace layout
│   │   ├── api.js                 # API + SSE client
│   │   ├── main.jsx               # React entry
│   │   └── styles.css             # Dark theme + glassmorphism
│   └── index.html
└── README.md
```

---

## Demo Scenarios

1. **Data Analysis**: `"Analyze sales.csv and provide top trends"`
2. **Calendar**: `"Schedule a team meeting tomorrow at 2pm"`
3. **Multi-step**: `"Summarize daily-report.txt and email to ops@example.com"`
4. **Search**: `"Search for workflow automation best practices"`
<img width="1915" height="1087" alt="image" src="https://github.com/user-attachments/assets/30d401fb-6e65-4b88-9f3f-02d9eaf68003" />
<img width="1918" height="1086" alt="image" src="https://github.com/user-attachments/assets/cc277fdc-291d-487f-a318-1725eb3e49bd" />
<img width="1910" height="1073" alt="image" src="https://github.com/user-attachments/assets/2a03e128-5332-4df9-84b5-ed571d001b63" />


---

## Scope and launch status

Kinetix is a single-workspace local demo, not a production multi-tenant service.
Production mode requires a JWT secret with at least 32 characters and a valid
Fernet key. Before public deployment, add user-data isolation, rate limiting,
reviewed database policies, provider approvals, and confirmation for external
actions. Prompts and selected file contents are sent to OpenRouter for
reasoning, so review provider terms before using sensitive information.

## License

MIT
