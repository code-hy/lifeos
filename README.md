# LifeOS — Autonomous Agentic Operating System

An AI-powered personal operating system that manages life tasks through a hierarchy of specialized agents, MCP (Model Context Protocol) tools, and a proactive "Antigravity" background loop.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI / CLI                      │
├─────────────┬───────────────┬───────────────────────┤
│  Executive  │  Proactive    │     MCP Server        │
│  Orchestrator│  Monitor     │  (Tool Registry)      │
│  (Gemini)   │  (Background) │                       │
├──────┼──────┴───────┼───────┴───────┬───────────────┤
│  Planner  │  Memory Agent  │  SecurityGuard         │
│  Agent    │  (ChromaDB)    │  (Zero-Trust)          │
├───────────┴───────────────┴─────────────────────────┤
│  Specialized Agents: Finance · Travel · Health       │
├─────────────────────────────────────────────────────┤
│  MCP Tools: Calendar · Gmail · Finance · Travel ·   │
│             Health                                   │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

| Component     | Technology                      |
|---------------|---------------------------------|
| LLM           | Google Gemini 2.0 Flash         |
| Backend       | FastAPI + Uvicorn               |
| CLI           | Typer + Rich                    |
| Vector Memory | ChromaDB (with Gemini embeddings) |
| Structured DB | SQLite                          |
| Protocol      | Model Context Protocol (MCP)    |
| Deployment    | Docker / Docker Compose         |

---

## Quick Start

### Prerequisites

- Python 3.11+
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 1. Setup

```bash
# Clone and enter the project
cd lifeos

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set up your Gemini API key
# Copy .env and add your key:
#   GEMINI_API_KEY=your_key_here
```

### 2. Run the Web Server

```bash
python main.py
# Or: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** for the dashboard UI.

### 3. Use the CLI

```bash
# Ask LifeOS a question
python cli.py ask "What's my checking account balance?"

# Approve a restricted tool call
python cli.py approve <approval-uuid>

# Reject a restricted tool call
python cli.py reject <approval-uuid>

# List pending approvals
python cli.py approvals

# View stored preferences
python cli.py memory-list

# Add a preference
python cli.py memory-add favorite_airline "United Airlines"

# Trigger a proactive event (requires server running)
python cli.py trigger-proactive flight_delay
```

---

## Testing the "Wow" Demo

Follow this script step by step to demonstrate the full LifeOS capability:

### Step 1: Launch the Dashboard

```bash
python main.py
```

Visit **http://localhost:8000**. You should see:
- Status indicators (Proactive Monitor: Active, Model: Gemini 2.0 Flash)
- Console panel for queries
- Memory Bank panel (right)
- Audit logs panel

### Step 2: Ask a Question

In the chat input at the center panel, type:

```
What's my checking account balance?
```

**Expected:** Executive Orchestrator plans and executes a `get_balance` tool call, returning all account balances.

### Step 3: Trigger a Proactive Event (The "Wow" Moment)

Click **"Utility Bill Alert"** on the left panel, OR run:

```bash
python cli.py trigger-proactive bill_spike
```

**Watch the logs** in the right panel and in the terminal. LifeOS will:
1. Detect the proactive trigger
2. Read unread emails to find the high electricity bill
3. Flag a **150% spending spike** ($452.12 vs $180 avg)
4. The **Finance Agent** recommends switching to `GridChoice Energy` (saves $58/month)
5. **Security Guard** places `send_email` on HOLD (requires approval)

### Step 4: Approve the Action

An **approval card** appears in the dashboard with a `send_email` tool requesting approval. Click **"Approve Call"** or run:

```bash
python cli.py approve <uuid>
```

**Result:** LifeOS completes the plan — it generates a summary comparing providers and "sends" the recommendation email.

### Step 5: Trigger Flight Delay

Click **"Flight Delay Notification"** or run:

```bash
python cli.py trigger-proactive flight_delay
```

**Expected:** LifeOS detects UA102 is delayed 180 minutes, checks calendar for conflicts ("Dinner with Wife" at 7 PM), reschedules events, and puts `send_email` on HOLD for approval to notify your wife.

### Step 6: Store a Preference

Type in the Memory Bank panel:
- Key: `favorite_airline`
- Value: `United Airlines`

Or run:
```bash
python cli.py memory-add favorite_airline "United Airlines"
```

Now when you ask flight-related questions, the Planner will have context of your airline preference.

---

## API Endpoints

### Query & Response
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ask` | Send a task/query to the Executive Orchestrator |
| `GET`  | `/api/approvals` | List all pending security approvals |
| `POST` | `/api/approvals/{id}/decide` | Approve/reject a pending tool call |

### Memory
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/memory` | Retrieve all stored user preferences |
| `POST` | `/api/memory` | Store a new preference |
| `POST` | `/api/memory/clear` | Clear all stored preferences |

### Proactive Loop
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/proactive/trigger` | Inject a life event (`flight_delay`, `bill_spike`, `workout_reminder`) |
| `GET`  | `/api/proactive/logs` | Get logs of autonomous background runs |

### Security
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/security/logs` | Get Security Guard audit trail |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/status` | System health, model info, and component status |

---

## MCP Tools

All tools live in `mcp/tools/` and are auto-discovered on startup:

| Tool                | Module      | Restricted | Description |
|---------------------|-------------|------------|-------------|
| `get_balance`       | finance.py  | No         | Query account balances |
| `transfer_funds`    | finance.py  | **Yes**    | Transfer money between accounts |
| `send_email`        | gmail.py    | **Yes**    | Send an email |
| `read_emails`       | gmail.py    | No         | Read inbox |
| `get_events`        | calendar.py | No         | List calendar events |
| `create_calendar_event` | calendar.py | No      | Create a new event |
| `delete_calendar`   | calendar.py | **Yes**    | Delete a calendar event |
| `check_flight_status`| travel.py  | No         | Check flight status |
| `book_flight`       | travel.py   | No         | Book a flight |
| `log_workout`       | health.py   | No         | Log exercise |
| `get_health_metrics`| health.py   | No         | Get health summary |

Tools marked **Restricted** require human-in-the-loop approval via the SecurityGuard interceptor.

---

## Project Structure

```
lifeos/
├── main.py                 # FastAPI entry point + routes
├── cli.py                  # Typer CLI for all operations
├── proactive_loop.py       # Background "Antigravity" monitor
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
├── docker-compose.yml      # Multi-service orchestration
├── .env                    # Configuration (API keys)
├── data/                   # SQLite + ChromaDB persistence
├── core/
│   ├── orchestrator.py     # Executive Agent (planning + execution)
│   ├── security.py         # SecurityGuard (zero-trust interceptor)
│   └── memory.py           # Long-term memory (ChromaDB + fallback)
├── agents/
│   ├── planner.py          # Task decomposition (LLM + rule-based)
│   └── specialized.py      # Finance, Travel, Health agents
├── mcp/
│   ├── server.py           # MCP server host + tool registry
│   └── tools/              # Tool definitions
│       ├── calendar.py     # Calendar event CRUD
│       ├── finance.py      # Balance + transfers
│       ├── gmail.py        # Email send/read
│       ├── health.py       # Workout + metrics
│       └── travel.py       # Flight status + booking
└── templates/
    └── index.html          # Dashboard UI
```

## Docker Deployment

```bash
# Build and run with Docker Compose
docker compose up --build

# Services:
#   - api: LifeOS on http://localhost:8000
#   - vector-db: ChromaDB on http://localhost:8001
```

## Configuration

Edit `.env` in the project root:

```ini
# Required: Get from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_key_here

# Optional: Model selection (default: gemini-2.0-flash)
GEMINI_MODEL=gemini-2.0-flash

# Optional: Remote ChromaDB (leave blank for local persistent storage)
CHROMA_DB_HOST=
CHROMA_DB_PORT=8000
```

Without a `GEMINI_API_KEY`, LifeOS runs in **offline mode** using a static rule-based planner and fallback deterministic embeddings. All core functionality (agents, tools, security, proactive loop) still works — just without LLM-generated natural language responses.

## How It Works

### Executive Orchestrator (`core/orchestrator.py`)
1. **Security Check** — Input validated against prompt injection patterns
2. **Memory Retrieval** — ChromaDB queried for relevant user preferences
3. **Planning** — LLM decomposes the request into tool/reasoning steps
4. **Execution** — Steps run sequentially; restricted tools pause for approval
5. **Synthesis** — Results compiled into a natural language response

### Security Interceptor (`mcp/server.py:execute_tool`)
Every MCP tool call passes through `SecurityGuard.validate_action()` before execution. Restricted tools (send_email, transfer_funds, delete_calendar) are automatically placed on HOLD requiring manual approval via the CLI or Dashboard.

### Proactive Loop (`proactive_loop.py`)
The "Antigravity" engine runs as a background asyncio task inside FastAPI. It:
- Listens for manual trigger events (flight_delay, bill_spike, workout_reminder)
- Processes them autonomously through the Executive Orchestrator
- Logs all events to SQLite for audit

### Memory Agent (`core/memory.py`)
- Uses ChromaDB for vector storage of user preferences
- Custom `GeminiEmbeddingFunction` with deterministic fallback
- Supports CRUD operations via API and CLI
- Falls back to in-memory JSON storage if ChromaDB is unavailable
