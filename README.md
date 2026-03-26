# 🔍 SiteScope — Agentic AI Red Flag Report Generator

**Arcadis Hackathon | Case 3: Automated Site Due Diligence using Distributed Geo Data**

Click a location on the map → get a structured Red Flag Report analyzing site risks from publicly available German geodata.

## Architecture

```
┌──────────────┐     POST /analyze      ┌──────────────────────┐
│   Next.js    │  ─────────────────────► │   FastAPI Backend    │
│   Frontend   │                         │                      │
│  (Mapbox GL) │  ◄───────────────────── │  ┌────────────────┐  │
│              │     Risk Assessment     │  │  Orchestrator   │  │
└──────────────┘         JSON            │  │  (asyncio)      │  │
                                         │  └───┬──┬──┬───────┘  │
                                         │      │  │  │          │
                                    ┌────┘  ┌───┘  │  └───┐     │
                                    ▼       ▼      ▼      ▼     │
                                  🌊      🌿    🏛️    📐 ⚡   │
                                 Flood  Nature Heritage (Stretch)│
                                 Agent  Agent  Agent            │
                                    │       │      │             │
                                    ▼       ▼      ▼             │
                              Bayern LfU WMS / BLfD WMS         │
                              (Public, no API keys)             │
                                         │                      │
                                         ▼                      │
                                  ┌──────────────┐             │
                                  │ Claude AI    │             │
                                  │ Report Gen.  │             │
                                  └──────────────┘             │
                                         │                      │
                                    Red Flag Report             │
                                    (JSON + PDF)                │
                                         └──────────────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your OPENROUTER_API_KEY and optional MAPBOX_TOKEN

# 2. Docker Compose (recommended)
docker compose up

# 3. Open http://localhost:3000
```

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

## Demo Locations (Bavaria)

| Location | Lat | Lng | Expected Red Flags |
|----------|-----|-----|--------------------|
| Isar/Flaucher, München | 48.116 | 11.557 | 🌊 Flood risk (HQ100 zone) |
| Marienplatz, München | 48.137 | 11.576 | 🏛️ Heritage (Ensemble Altstadt) |
| Englischer Garten | 48.164 | 11.605 | 🌿 Nature (LSG), 🌊 Isar flood |
| Nymphenburger Schloss | 48.158 | 11.503 | 🏛️ Heritage, 🌿 Nature |
| Olympiapark | 48.175 | 11.552 | 🏛️ Heritage (Ensemble) |

## Agents

| Agent | Status | Data Sources |
|-------|--------|-------------|
| 🌊 Flood & Water | MVP | LfU Überschwemmungsgebiete, Wassertiefen, Oberflächenabfluss |
| 🌿 Nature & Environment | MVP | LfU Schutzgebiete, Geotope, Trinkwasserschutz, Bodenschätzung |
| 🏛️ Heritage / Monuments | MVP | BLfD Denkmäler (Einzel-, Boden-, Bauensemble, Landschaft) |
| 📐 Zoning & Land Use | Stretch | Flächennutzungspläne, Climate data |
| ⚡ Infrastructure | Stretch | Grid connectivity, Elevation data |

## Tech Stack

- **Frontend:** Next.js 14 (App Router) + Mapbox GL JS + Tailwind CSS
- **Backend:** Python FastAPI + httpx (async HTTP) + Anthropic SDK
- **Geo Services:** WMS/WFS (Bayern LfU, BLfD) — free, no API keys
- **AI:** MiniMax M2.5 via OpenRouter (free tier!) for report generation
- **PDF:** WeasyPrint for HTML→PDF export
- **Deploy:** Docker Compose

## API

### `POST /api/analyze`
```json
{
  "lat": 48.137,
  "lng": 11.576
}
```

Response: Structured risk assessment with per-category results.

### `POST /api/report/pdf`
```json
{
  "lat": 48.137,
  "lng": 11.576
}
```

Response: PDF download of the Red Flag Report.

## Team

Built at the Arcadis Hackathon 2026.
