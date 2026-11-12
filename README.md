# Wedding Planner — LangGraph Multi-Agent AI

An AI wedding coordinator that delegates to flight, venue and playlist specialists.

## Architecture

`AgentChat UI (Vercel) -> LangGraph Server (wedding_planner graph) -> Groq LLM`

- Flight specialist: Kiwi remote MCP `search-flight`
- Venue specialist: Tavily web search
- Playlist specialist: read-only bundled Chinook SQLite catalog
- Conversations: LangGraph threads/checkpoint persistence (managed by LangGraph Server)

**Important:** The bundled Chinook database is a sample music catalog, **not** the chat-history database. Local `langgraph dev` is for development; use a supported persistent LangGraph deployment for production threads. This project does not make real bookings.

## 1. Local setup (Windows PowerShell)

Requires Python 3.11 or 3.12, Git, and API keys for Groq and Tavily.

```powershell
cd wedding-planner-agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
Copy-Item .env.example .env
```

Edit `.env` with `GROQ_API_KEY` and `TAVILY_API_KEY`. **Never commit `.env`.**

## 2. Start LangGraph Server locally

```powershell
langgraph dev
```

Typically the local API is `http://127.0.0.1:2024`; inspect terminal output for the actual URL. `langgraph.json` exposes graph ID **`wedding_planner`**. The dev server provides threads and local persistence for testing; do not treat it as a production database.

Test in LangGraph Studio (link printed by CLI) or use the API:

```powershell
curl.exe -X POST http://127.0.0.1:2024/threads -H "Content-Type: application/json" -d "{}"
```

Save the returned `thread_id` and use it for subsequent turns. For a simple one-off run:

```powershell
curl.exe -X POST http://127.0.0.1:2024/runs/wait -H "Content-Type: application/json" -d '{"assistant_id":"wedding_planner","input":{"messages":[{"role":"user","content":"Help plan a wedding in Rome"}]}}'
```

PowerShell quoting can vary; using Studio/AgentChat UI is easier for interactive testing.

## 3. AgentChat UI (local)

Use the official UI source: https://github.com/langchain-ai/agent-chat-ui

```powershell
cd ..
git clone https://github.com/langchain-ai/agent-chat-ui.git
cd agent-chat-ui
npm install
npm run dev
```

In the UI's connection settings, enter the LangGraph Server URL (usually `http://localhost:2024`) and graph/assistant ID `wedding_planner`. For local dev without auth, leave the API key empty where supported. Check the UI repo's current README for its supported environment variables and setup options; they may change by release.

Use **New Chat** for a new thread and return to earlier threads via the UI's thread history where supported. The actual persistence comes from the server, not the browser.

## 4. GitHub

```powershell
cd ..\wedding-planner-agent
git init
git add .
git status
git commit -m "Initial Wedding Planner LangGraph project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/wedding-planner-agent.git
git push -u origin main
```

Create an empty GitHub repository before pushing. Confirm `.env` is not tracked. The included Chinook DB is a demo dataset, so review its provenance/license before public distribution.

## 5. Production deployment

**Recommended:** deploy the `wedding_planner` graph using a supported **LangSmith / LangGraph Deployment** from your GitHub repository. Configure `GROQ_API_KEY`, `TAVILY_API_KEY`, and optional `KIWI_MCP_URL` as deployment secrets. Use the deployment's managed persistent thread/checkpoint service and note its authentication policy. Verify flight MCP reachability from the hosted runtime.

Then fork/deploy the official AgentChat UI to **Vercel** following its current README and configure it to connect to your deployed LangGraph API URL, graph ID `wedding_planner`, and the authentication method required by your backend. Do **not** put a private server API key in publicly exposed browser environment variables; use an appropriate auth/proxy arrangement. Configure allowed origins/CORS and verify streaming and thread history.

Self-hosted LangGraph production may require additional infrastructure and licensing; do not deploy `langgraph dev` as a public production server. Check current LangGraph deployment plan requirements and costs before choosing a hosting option.

## 6. Acceptance checklist

- [ ] `langgraph dev` starts and `wedding_planner` graph appears
- [ ] Coordinator asks for missing preferences and saves them
- [ ] Venue specialist searches Tavily successfully
- [ ] Playlist specialist returns tracks from Chinook
- [ ] Flight specialist connects to Kiwi MCP (or reports unavailable without inventing prices)
- [ ] UI can stream messages
- [ ] A new chat has a new thread ID
- [ ] Old chat survives restart on persistent production deployment
- [ ] API keys are not committed or exposed in browser

## Known limitations

- Groq model tool-call support can vary by model/provider version; validate all four tools.
- Flight tool names and remote MCP behavior can change; test before deployment.
- The bundled music catalog is static and may not contain every genre.
- SQLite query protection includes read-only connection, `query_only` pragma, single-SELECT validation, and result limits; do not expose arbitrary SQL to untrusted public users without additional hardening.
- No real payment, reservation or vendor booking is performed.

## 7. Offline validation before pushing

With your virtual environment active, run:

```powershell
python -m pip install pytest
python -m pytest -q
python -m compileall -q app tests
```

Then run `git status --short` and `git diff --cached --name-only` to review staged files. Do not publish `.env`, local logs, traces, or private chat records. The repository does not contain the AgentChat UI source; clone the official frontend separately.

**Status of prior manual testing:** The developer reported that all four local chat-history tests passed and the coordinator invoked state, venue, playlist, and flight tools. Flight lookup returned requests for a departure date instead of actual itineraries; that remains a known limitation. These reports are not automated integration tests.

**Database redistribution:** Verify the Chinook sample database's redistribution terms before making this repository public. If uncertain, omit `resources/Chinook.db` from the public repository and document where to obtain it; the bundled database is currently required for playlist recommendations.
