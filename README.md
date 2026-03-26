# SiteScope

Agentic site due diligence prototype for Bavaria, Germany.

Click a point on the map and SiteScope runs multiple geodata agents in parallel, synthesizes the findings into a Red Flag Report, and can export the result as PDF.

This README describes the current implementation as it exists in code, including exact request counts and where LLM calls really happen.

## What The App Does Today

- Frontend: Next.js 14 + MapLibre GL with OpenStreetMap raster tiles
- Backend: FastAPI
- Geography scope: Bavaria only
- Analysis mode: point-based screening around the clicked coordinate
- AI usage: exactly one LLM synthesis call per analysis run, not per agent
- Report output: JSON report in the UI, optional PDF export

## Real Architecture

```text
Browser click
  -> POST /api/analyze
    -> Bavaria bounding-box check
    -> Orchestrator(include_stretch=True)
    -> 5 agents run concurrently
      -> FloodAgent          -> 12 WMS GetFeatureInfo requests
      -> NatureAgent         -> 17 WMS GetFeatureInfo requests
      -> HeritageAgent       ->  4 WMS GetFeatureInfo requests
      -> ZoningAgent         ->  4 WMS GetFeatureInfo requests + 1 Open-Meteo request
      -> InfraAgent          -> 18 WMS GetFeatureInfo requests + 1 OpenTopoData request
    -> ReportGenerator
      -> 1 OpenRouter chat.completions request to minimax/minimax-m2.5
      -> fallback to rule-based report if no API key or LLM failure
    -> AnalyzeResponse JSON

Optional PDF download
  -> POST /api/report/pdf
    -> runs the full analysis again
    -> renders PDF locally with Jinja2 + WeasyPrint
```

## Exact Request Counts

### 1. `POST /api/analyze`

If the coordinate is inside Bavaria, the backend currently makes:

- 55 WMS `GetFeatureInfo` requests
- 1 Open-Meteo REST request
- 1 OpenTopoData REST request
- 1 OpenRouter LLM request, but only if `OPENROUTER_API_KEY` is set

That means:

- With OpenRouter key: 58 outbound requests total
- Without OpenRouter key: 57 outbound requests total

Important details:

- The 5 agents run concurrently via `asyncio.gather`.
- Each WMS layer is queried individually.
- There are no agent-level LLM calls.
- There are no retries, no tool-calling, and no multi-step LLM chain.

### 2. `POST /api/report/pdf`

The PDF endpoint does not reuse a previous analysis result.

It runs the entire analysis again and then renders the PDF locally. So one PDF export adds:

- 55 more WMS requests
- 1 more Open-Meteo request
- 1 more OpenTopoData request
- 1 more OpenRouter LLM request if the key is set

### 3. Typical UI session: analyze, then download PDF

If a user clicks once and then downloads the PDF:

- Browser -> backend requests: 2
- Backend outbound requests with OpenRouter enabled: 116 total
- Backend outbound requests without OpenRouter enabled: 114 total

### 4. When zero analysis requests happen

If the clicked coordinate is outside Bavaria, the backend returns early after the bounding-box check:

- 0 WMS requests
- 0 REST geodata requests
- 0 LLM requests

## Where The LLM Is Used

There is currently only one LLM integration in the whole analysis path:

- File: `backend/report_generator.py`
- Provider: OpenRouter
- Model: `minimax/minimax-m2.5`
- SDK call: `client.chat.completions.create(...)`
- Messages: 1 system prompt + 1 user prompt
- Temperature: `0.3`
- Max tokens: `2000`

The LLM is used only for:

- executive summary
- overall risk level
- key red flags
- recommended actions per category

The LLM is not used for:

- extracting geodata
- querying map services
- classifying individual layers
- deciding which agents run

If the OpenRouter key is missing, or the LLM returns invalid JSON, the code falls back to a rule-based report builder and still returns a report.

## Agent And Source Breakdown

All 5 agents run on every analysis request because both API endpoints instantiate:

```python
Orchestrator(include_stretch=True)
```

So even the two "stretch" agents are currently always enabled.

| Agent | Current status in code | External calls per run | Notes |
| --- | --- | ---: | --- |
| FloodAgent | active | 12 WMS | Flood zones, water depths, surface runoff, avalanche cadastre |
| NatureAgent | active | 17 WMS | Protected areas, geotopes, water protection, soil function, biotopes, eco cadastre |
| HeritageAgent | active | 4 WMS | BLfD monument data via GML `GetFeatureInfo` |
| ZoningAgent | active | 4 WMS + 1 REST | Noise maps, extraction areas, plus 2023 climate context from Open-Meteo |
| InfraAgent | active | 18 WMS + 1 REST | Georisks, geology, hydrogeology, soils, geothermal, plus elevation from OpenTopoData |

### Layer counts behind those numbers

- Flood: `4 + 4 + 2 + 2 = 12`
- Nature: `6 + 1 + 2 + 1 + 3 + 4 = 17`
- Heritage: `4`
- Zoning: `2 + 2 = 4`
- Infrastructure: `7 + 1 + 2 + 3 + 1 + 1 + 3 = 18`

Total WMS layer queries per analysis: `12 + 17 + 4 + 4 + 18 = 55`

## Request Flow In More Detail

1. The frontend sends `POST /api/analyze` with `{ "lat": ..., "lng": ... }`.
2. The backend checks whether the coordinate is inside the Bavaria bounding box.
3. The orchestrator creates all five agents.
4. Each agent queries its configured WMS layers individually.
5. Zoning additionally calls Open-Meteo once.
6. Infrastructure additionally calls OpenTopoData once.
7. Each agent returns an `AgentResult` with:
   - `risk_level`
   - `summary`
   - `findings`
   - `layers_queried`
   - `layers_with_data`
   - `errors`
   - `execution_time_ms`
8. The report generator formats all agent results into one large prompt.
9. Exactly one LLM request synthesizes the final narrative report.
10. The LLM output is merged back into the structured per-category data.
11. The API returns both:
   - raw agent results
   - synthesized final report

## API Endpoints

### `POST /api/analyze`

Runs the full analysis and returns JSON.

Request:

```json
{
  "lat": 48.137,
  "lng": 11.576
}
```

Response shape:

```json
{
  "success": true,
  "report": {
    "lat": 48.137,
    "lng": 11.576,
    "overall_risk_level": "MEDIUM",
    "executive_summary": "..."
  },
  "agent_results": [
    {
      "category": "flood",
      "agent_name": "Flood & Water Agent",
      "risk_level": "NONE",
      "layers_queried": 12,
      "layers_with_data": 0,
      "execution_time_ms": 642
    }
  ],
  "errors": []
}
```

### `POST /api/report/pdf`

Runs the full analysis again and returns a downloadable PDF.

Request:

```json
{
  "lat": 48.137,
  "lng": 11.576
}
```

### `GET /api/demo`

Returns the built-in demo locations shown in the UI.

### `GET /health`

Basic health endpoint.

### `GET /api/debug/sources`

Diagnostics route that tests all configured external sources concurrently, including:

- WMS services used by the agents
- one monitoring-only WMS source that is not part of the analysis flow
- Open-Meteo
- OpenTopoData
- OpenRouter model listing

## Important Implementation Notes

### 1. `report.total_layers_queried` is not the canonical technical count

The final `report.total_layers_queried` field is currently derived from the number of findings merged into the report, not from the true number of WMS layers queried.

For exact operational counts, use:

- `agent_results[*].layers_queried`

### 2. `MAX_AGENTS_PARALLEL` exists but is not currently enforced

The setting exists in config, but the orchestrator currently launches all agents together with `asyncio.gather(...)` without applying a concurrency limit.

### 3. Partial success is supported

If one or more external sources fail:

- the affected agent can still return partial findings
- errors are accumulated in `errors`
- the report may still be generated

### 4. Fallback mode is real, not just theoretical

Without `OPENROUTER_API_KEY`, the app still works:

- agents still run
- geodata still gets queried
- the final narrative report is created by deterministic fallback code

The executive summary still exists in fallback mode, but it is generated by deterministic code and category recommendations remain much simpler.

### 5. Bavaria-only coverage is enforced server-side

The backend rejects coordinates outside this approximate box:

- latitude: `47.27` to `50.56`
- longitude: `8.97` to `13.84`

### 6. `NEXT_PUBLIC_API_URL` is a browser-facing setting

The frontend fetches from `NEXT_PUBLIC_API_URL` directly when it is set.

For same-origin setups, leave it empty so requests go to `/api/...` and can be rewritten or proxied by Next.js / nginx.

## Tech Stack

- Frontend: Next.js 14, React 18, TypeScript, Tailwind, MapLibre GL
- Backend: FastAPI, Pydantic, httpx
- LLM: OpenRouter via OpenAI SDK
- Model in current code: `minimax/minimax-m2.5`
- Geodata: Bayern LfU and BLfD WMS services
- Extra APIs: Open-Meteo, OpenTopoData
- PDF: Jinja2 + WeasyPrint
- Deployment: Docker Compose

## Quick Start

### Docker Compose

```bash
cp .env.example .env
# Add your OPENROUTER_API_KEY if you want LLM synthesis

docker compose up --build
```

Open:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)

### Manual Setup

Backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

Example values are in `.env.example`.

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | no | Enables the single LLM synthesis call per analysis |
| `NEXT_PUBLIC_API_URL` | no | Browser-facing frontend API base URL; leave empty for same-origin `/api` proxying |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | no | Present in `.env.example`, but the current frontend map uses OSM raster tiles and does not read this variable |
| `BACKEND_HOST` | no | FastAPI bind host |
| `BACKEND_PORT` | no | FastAPI bind port |
| `WMS_TIMEOUT` | no | Timeout for WMS requests |
| `MAX_AGENTS_PARALLEL` | no | Present in config but not currently applied in orchestrator |

## Demo Locations

| Location | Lat | Lng | Typical findings |
| --- | ---: | ---: | --- |
| Isar/Flaucher, München | 48.116 | 11.557 | Flood |
| Marienplatz, München | 48.137 | 11.576 | Heritage |
| Englischer Garten | 48.164 | 11.605 | Nature, Flood |
| Nymphenburger Schloss | 48.158 | 11.503 | Heritage, Nature |
| Olympiapark | 48.175 | 11.552 | Heritage |

## Repository Layout

```text
frontend/
  app/                  Next.js app router pages
  components/           map, report panel, badges
  lib/                  API client and shared TS types

backend/
  agents/               per-domain analysis agents
  geo/                  WMS client, parsers, CRS transforms
  templates/            HTML template for PDF rendering
  main.py               FastAPI entrypoint
  orchestrator.py       parallel agent dispatch
  report_generator.py   single LLM synthesis step + fallback
  pdf_export.py         HTML -> PDF rendering

docs/
  api-sources.md        source reference notes
```

## Current Limitations

- No caching: repeated clicks on the same coordinate rerun the whole pipeline.
- No reuse between JSON analysis and PDF export.
- Zoning and infrastructure are still partly placeholder/stretch in terms of interpretation depth, even though they run on every request.
- Coverage is limited to Bavaria and to the currently configured public sources.
- The system is a screening tool, not a legal, planning, or environmental sign-off.
