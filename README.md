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
- [x] **Step 2** — Report engine (Groq primary + Gemini fallback, with
      retries), `/health/groq`, `/health/gemini`
- [x] **Step 3** — `/api/v1/generate-report` endpoint + `/health/all`
- [x] **Step 4** — Production hardening (rate limiting, global exception
      handler, request logging, mocked fallback-logic tests)

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

## Step 2 — Report engine (Groq + Gemini)

`app/services/report_engine.py` fixes three reference-doc bugs:

1. **Blocking sync client** — the reference doc's `Groq()` client was
   called with no `await` inside an `async def`, which blocks the whole
   event loop for the HTTP call's duration. Fixed with `AsyncGroq`.
2. **Dead `tenacity` dependency** — now Groq actually gets
   `GROQ_MAX_RETRIES` attempts (exponential backoff) before falling back
   to Gemini, instead of any single hiccup immediately triggering
   fallback.
3. **`print()` instead of logging** — the fallback-triggered warning now
   goes through the structured logger.

```powershell
docker compose up -d --build
curl.exe http://localhost:8003/health/groq
curl.exe http://localhost:8003/health/gemini
```

Expected:
```json
{"status":"ok","model":"llama-3.1-70b-versatile"}
{"status":"ok","model":"gemini-1.5-flash"}
```

Both make one real (tiny) API call each — don't poll them tightly.

## Step 3 — Full report generation

**Prerequisite:** `fireguard-agent-compliance` running (for `/health/all`
only — `/api/v1/generate-report` itself doesn't call it, since this
service is called WITH compliance's output already, not asked to fetch
it).

```powershell
docker compose up -d --build
curl.exe http://localhost:8003/health/all
```

```powershell
$body = @{
    building_name = "Grand Central Tower"
    audit_data = @{
        overall_status = "COMPLIANT"
        compliance_score = 100.0
        detailed_checks = @(
            @{
                rule_clause = "Chapter 3 (Page 51)"
                status = "COMPLIANT"
                finding = "The building has 5 floors. The regulation requires a refuge floor for every 10 floors; therefore, no refuge floor is required."
                recommendation = "Maintain regular stairwell exit checks."
            }
        )
        summary = "Building fully satisfies all evaluated fire safety regulations."
    }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://localhost:8003/api/v1/generate-report" -Method Post -Body $body -ContentType "application/json"
```

Expected: `building_name`, `overall_status`, `compliance_score`,
`executive_summary_markdown` (a full Markdown report — headings, bullet
points, callouts per the prompt's structure), `generated_by` (confirms
which LLM actually produced it).

## Step 4 — Production hardening

**1. Rate limiting** (`slowapi`) — `/api/v1/generate-report` throttled
(`REPORT_RATE_LIMIT`, default `10/minute`) to protect both Groq and
Gemini quota. Same gotcha as `fireguard-agent-compliance`: slowapi's
`@limiter.limit()` looks up the Starlette `Request` param by the literal
name `request`, so the request body param is named `report_request`
instead of `request` (which the reference doc used, and which would
have silently broken rate limiting).

**2. Global exception handler** — a final backstop so an unexpected bug
can never leak a raw traceback to a client.

**3. Request logging middleware** (`app/middleware.py`).

**4. Mocked fallback-logic tests** — no real API keys/clients needed:

```powershell
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

`tests/test_report_engine.py` verifies: Groq succeeding means Gemini is
never called; Groq failing triggers the Gemini fallback and the response
says so (`generated_by` contains `"fallback"`); both failing raises
`ReportEngineError`.
