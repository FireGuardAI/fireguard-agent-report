# fireguard-agent-report

The executive presentation layer of the FireGuard platform — takes
`fireguard-agent-compliance`'s structured JSON audit output and
generates a formal, client-facing Fire Safety Executive Report in
Markdown. Primary LLM: Groq Llama 3.1 70B (fast, high-quality narrative
generation). Automatic fallback to Gemini 1.5 Flash if Groq is
rate-limited or unavailable.

## Build status

- [x] **Step 1** — FastAPI skeleton, config/logger/exceptions, `/health`,
      Dockerized + joined to `fireguard-vector-store`'s Docker network
- [ ] Step 2 — Report engine (Groq primary + Gemini fallback, with retries)
- [ ] Step 3 — `/api/v1/generate-report` endpoint + `/health/all`
- [ ] Step 4 — Production hardening

## Prerequisites

- A free Groq API key: https://console.groq.com/keys
- A free Gemini API key: https://aistudio.google.com/apikey
- `fireguard-agent-compliance` running (for `/health/all` in Step 3 —
  not required for Steps 1-2)

## Step 1 — Run locally

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env
# edit .env and set GROQ_API_KEY and GEMINI_API_KEY (both required)

uvicorn app.main:app --reload --port 8003
```

Test it:
```bash
curl.exe http://localhost:8003/health
```
Expected:
```json
{"status":"ok","service":"FireGuard Report Generation Agent"}
```

## Step 1 — Run with Docker

```powershell
Copy-Item .env.example .env
# edit .env and set both API keys
docker compose up -d --build
```

Test it:
```powershell
curl.exe http://localhost:8003/health
docker ps   # fireguard-agent-report should show (healthy)
```

If it fails with a "network not found" error, see the same
troubleshooting note in `fireguard-agent-retrieval`'s README.

Port `8003` — `8000` is ChromaDB, `8001` is `fireguard-agent-retrieval`,
`8002` is `fireguard-agent-compliance`, `8004` is `fireguard-agent-intake`.
