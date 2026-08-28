# NoteFlow — Personal Voice-to-Notion Capture Agent

**NoteFlow** is a streamlined personal voice-note capture assistant. Speak a raw thought into the web interface, and the system:
1. Transcribes audio via **Groq Whisper** (`whisper-large-v3-turbo`).
2. Dispatches the transcript to a **LangGraph tool-calling agent** powered by **Gemini 2.5 Flash** with direct access to your Notion workspace via **Notion's remote MCP server** (`https://mcp.notion.com/mcp`).
3. Formats and files the thought appropriately (searching existing pages/databases or creating an Inbox entry).
4. Generates and plays back a spoken natural-language confirmation via **`edge-tts`**.

---

## ⚡ Quickstart

### 1. Prerequisites
- [uv](https://github.com/astral-sh/uv) (Fast Python package and project manager)
- Python 3.10+
- Google AI Studio API key (`GOOGLE_API_KEY`)
- Groq API key (`GROQ_API_KEY`)

### 2. Setup Environment Variables
Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

> **Note on Notion Authorization**: Notion access is handled via OAuth directly through the official remote MCP server (`https://mcp.notion.com/mcp`). On first run or connection, an OAuth browser handshake will authenticate your Notion workspace.

### 3. Install Dependencies
```bash
uv sync
```

### 4. Run the Application
```bash
uv run uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` (or `http://<your-lan-ip>:8000` on your mobile phone on the same local network) to record and file voice notes.

---

## 📁 Repository Structure

```
NoteFlow_Simple/
├── pyproject.toml         # Dependencies & project config
├── uv.lock                # Pinned lockfile
├── .env.example           # Environment template
├── .env                   # Local API keys (ignored from git)
├── README.md              # Documentation
├── agent/                 # Agent logic & Prompts
│   ├── __init__.py        # Exports build_agent and process_note
│   ├── agent.py           # LangGraph create_react_agent + Notion MCP tools
│   └── prompts.py         # Notion filing system prompt
└── app/                   # Backend Web Service & Frontend Assets
    ├── main.py            # FastAPI app + routes + static mount
    ├── config.py          # Pydantic Settings (.env loader)
    ├── stt.py             # Groq Whisper STT async transcription
    ├── tts.py             # edge-tts voice synthesis
    └── static/
        ├── index.html     # Web UI with microphone & text input
        ├── style.css      # Dark glassmorphic styling
        └── app.js         # Recording, API calls, and audio playback
```

---

## 🛠 API Endpoints

- `POST /api/voice-note`: Accepts `audio` (multipart file) or `text` (form field), returns `{ transcript, confirmation_text, confirmation_audio_url }`.
- `GET /api/audio/latest.mp3`: Streams the latest synthesized audio.
- `GET /api/health`: Verifies server status and API key configuration.
- `GET /`: Serves the NoteFlow web UI.
