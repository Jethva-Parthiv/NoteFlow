# NoteFlow — High-Speed Voice-to-Notion Capture Agent

**NoteFlow** is an ultra-fast, intelligent personal voice-note capture assistant. Speak a raw thought into the web interface, and NoteFlow automatically structures, formats, and files it directly into your Notion workspace in seconds.

---

## 🚀 Key Features & Architecture

* **Plan-Once Fast-Path Execution**: Instead of multi-turn exploratory round-trips, the agent constructs and emits full formatted Markdown payloads (headings, checkboxes, bullet lists) directly in turn 1 using `notion-create-pages`.
* **Workspace Pre-Caching**: Root pages and databases are cached in-memory (`agent/cache.py`) using `notion-list-private-pages` and `notion-list-shared-pages`, eliminating search latency on common filing destinations.
* **Idempotent Duplicate Tool Call Interceptor**: Prevents repetitive tool loops in real time by trapping identical tool executions and instructing the model to pivot or finalize.
* **Recursion Circuit Breaker**: Graph recursion limit with graceful exception fallbacks ensures the agent never freezes on edge cases or ambiguous speech.
* **Robust Speech-to-Text (STT)**: Powered by Groq Whisper Large v3 Turbo, pinned to English with zero temperature and a domain vocabulary prompt hint to eliminate foreign-language hallucinations and acoustic misspellings.
* **Remote Notion MCP Protocol**: Connects securely to official Notion tools via `mcp-remote` over stdio.
* **Spoken Audio Confirmation**: Synthesizes and plays back natural spoken confirmations (under 15 words) using `edge-tts`.
* **Full Observability**: Optional first-class tracing with LangSmith.

---

## ⚡ Quickstart

### 1. Prerequisites
* [uv](https://github.com/astral-sh/uv) (Fast Python package and project manager)
* Node.js / `npx` (required for Notion MCP remote stdio transport)
* Python 3.10+
* Google AI Studio API key (`GOOGLE_API_KEY`)
* Groq API key (`GROQ_API_KEY`)

### 2. Setup Environment Variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your API keys in `.env`:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite

GROQ_API_KEY=your_groq_api_key_here

# Optional: LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key_here
LANGCHAIN_PROJECT=NoteFlow
```

### 3. Install Dependencies
```bash
uv sync
```

### 4. Run the Application
```bash
uv run uvicorn app.main:app --reload --port 8000
```

> **First Run Notion Authorization**:
> On initial startup or tool invocation, `mcp-remote` will open your default browser to authorize NoteFlow with your Notion workspace via OAuth. Once granted, tokens are cached locally.

Open `http://localhost:8000` (or `http://<your-lan-ip>:8000` on your phone on the same Wi-Fi) to start capturing voice notes.

---

## 📁 Repository Structure

```
NoteFlow_Simple/
├── pyproject.toml         # Dependencies & project config
├── uv.lock                # Pinned lockfile
├── .env.example           # Environment template
├── .env                   # Local API keys (git-ignored)
├── README.md              # Project documentation
├── agent/                 # Agent Logic, Routing & Tools
│   ├── __init__.py        # Agent exports
│   ├── agent.py           # LangGraph StateGraph + duplicate interceptor + circuit breaker
│   ├── cache.py           # In-memory TTL cache for Notion workspace root pages
│   ├── mcp.py             # Notion Remote MCP client connection & tools
│   └── prompts.py         # System prompt with fast-path, anti-loop & honesty guardrails
└── app/                   # Web Application & Audio Services
    ├── main.py            # FastAPI service + audio upload routes + static mount
    ├── config.py          # Pydantic Settings & environment loader
    ├── stt.py             # Groq Whisper Large v3 Turbo transcription
    ├── tts.py             # Microsoft edge-tts voice synthesis
    └── static/
        ├── index.html     # Web UI with voice recording & text fallback
        ├── style.css      # Dark glassmorphic interface
        └── app.js         # Audio recording, API requests & player
```

---

## 🛠 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/voice-note` | Accepts `audio` (multipart file) or `text` (form field), returns `{ transcript, confirmation_text, confirmation_audio_url }` |
| `GET` | `/api/audio/latest.mp3` | Streams the latest synthesized speech confirmation |
| `GET` | `/api/health` | Health check verifying API keys and server status |
| `GET` | `/` | Serves the NoteFlow web interface |
