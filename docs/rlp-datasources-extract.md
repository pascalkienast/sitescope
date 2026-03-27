# RLP Datasources Extract

Kuratierter Extrakt aus `origin/feature/rlp-datasources` zum manuellen Port nach `main`.

Stand des Branches bei der Auswertung: `64575fe` (`feat: display GetMap preview images in debug page for WMS services`).

## Relevante Commits

- `61b4bbc` `feat: Add RLP data source support with polygon selection`
- `3aa2d41` `feat: add RLP sources to debug diagnostics endpoint`
- `cea417a` `fix: remove RLP sources from auto-testing (services don't return meaningful diagnostic data at arbitrary test points)`
- `5f11e7d` `fix: update RLP services with correct URLs and re-add to debug endpoint`
- `1b8a2c0` `fix: use GetMap probe for all RLP services based on research`
- `ee6e217` `fix: use correct BBOX based on service CRS (EPSG:4326 vs EPSG:25832)`
- `64575fe` `feat: display GetMap preview images in debug page for WMS services`

## Was Du Aus Dem Branch Wirklich Brauchst

### 1. Datasource-Konfiguration

Das ist der eigentliche Kern des Branches. Diese Konstanten wurden in `backend/config.py` ergänzt:

```python
RLP_BBOX = {
    "lat_min": 48.9,
    "lat_max": 51.0,
    "lng_min": 6.0,
    "lng_max": 8.5,
}

RLP_TEST_LAT = 50.353
RLP_TEST_LNG = 7.597

RLP_EPSG25832_X = 402000.0
RLP_EPSG25832_Y = 5580000.0

WMS_RLP_LAND_VALUES = {
    "boris_rlp": _wms_service(
        "https://geo5.service24.rlp.de/wms/RLP_VBORISFREE2026.fcgi?",
        "VBORIS RLP Bodenrichtwerte (Land Values)",
        ["Bodenrichtwerte_Basis_RLP", "RLP_1"],
        version="1.1.1",
        crs="EPSG:25832",
        info_format=GML_INFO_FORMAT,
        probe="get_map",
    ),
}

WMS_RLP_HERITAGE = {
    "denkmal_rlp": _wms_service(
        "https://www.geoportal.rlp.de/owsproxy/00000000000000000000000000000000/9c9d7fe2c25527a5cb22cf9ca2266d26?",
        "GDKE RLP Denkmalkartierung (Heritage)",
        [
            "pgis_landesdenkmalpflege_sld",
            "denkmalzonen",
            "bga",
            "edm_flaechen",
            "edm_linien",
            "edm_punkte",
        ],
        version="1.1.1",
        crs="EPSG:4326",
        info_format=GML_INFO_FORMAT,
        probe="get_map",
    ),
}

WMS_RLP_NATURE = {
    "schutzgebiete_inspire": _wms_service(
        "https://inspire.naturschutz.rlp.de/cgi-bin/wfs/ps_wms?language=ger&",
        "INSPIRE Schutzgebiete RLP (Nature) - monitoring only",
        ["PS.ProtectedSitesSpecialAreaOfConservation"],
        version="1.1.1",
        crs="EPSG:4326",
        info_format=GML_INFO_FORMAT,
        probe="get_map",
    ),
}

WMS_RLP_FLOOD = {
    "ueberschwemmungsgebiete_rlp": _wms_service(
        "https://geodienste-wasser.rlp-umwelt.de/maps/uesg/wms?",
        "RLP Gesetzlich festgesetzte Überschwemmungsgebiete",
        ["uesg_gesetzlich"],
        version="1.1.1",
        crs="EPSG:4326",
        info_format=GML_INFO_FORMAT,
        probe="get_map",
    ),
    "hochwassergefahrenkarte_rlp": _wms_service(
        "https://geodienste-wasser.rlp-umwelt.de/maps/HWGK/wms?",
        "RLP Hochwassergefahrenkarte (HQ100 depths)",
        ["Ueberflutungsflaechen_HQ_100"],
        version="1.1.1",
        crs="EPSG:4326",
        info_format=GML_INFO_FORMAT,
        probe="get_map",
    ),
}

WMS_RLP_DIAGNOSTIC_SOURCE_GROUPS = (
    ("RLP-LandValues", WMS_RLP_LAND_VALUES),
    ("RLP-Heritage", WMS_RLP_HERITAGE),
    ("RLP-Nature", WMS_RLP_NATURE),
    ("RLP-Flood", WMS_RLP_FLOOD),
)
```

### 2. Neue Agent-Dateien

Diese Dateien wurden neu angelegt und enthalten die RLP-spezifische Interpretation:

- `backend/agents/rlp_agents.py`
- `backend/agents/rlp_flood_agent.py`
- `backend/agents/rlp_nature_agent.py`
- `backend/agents/rlp_heritage_agent.py`
- `backend/agents/rlp_land_value_agent.py`

Für einen manuellen Port sind das die wichtigsten neuen Dateien.

### 3. API-/Routing-Idee

Im Branch wurde in `backend/main.py` die Regionserkennung direkt über Bounding Boxes gemacht:

```python
def _is_in_rlp(lat: float, lng: float) -> bool:
    return (
        RLP_BBOX["lat_min"] <= lat <= RLP_BBOX["lat_max"]
        and RLP_BBOX["lng_min"] <= lng <= RLP_BBOX["lng_max"]
    )

region = None
if _is_in_bavaria(request.lat, request.lng):
    region = "BAVARIA"
elif _is_in_rlp(request.lat, request.lng):
    region = "RLP"
```

Danach wurde `Orchestrator(include_stretch=True, region=region)` verwendet.

## Was Du Nicht 1:1 Aus Dem Branch Übernehmen Solltest

### `backend/orchestrator.py`

Nicht wholesale übernehmen.

Grund:

- `main` hat inzwischen `analyze_without_report()` und die Buffer-Logik für die Flächenanalyse.
- Der Feature-Branch ersetzt den Orchestrator stattdessen durch eine Region/Pipeline-Variante.
- Ein blindes Überschreiben würde wahrscheinlich die aktuelle Area-Analyse in `main` brechen.

Empfehlung:

- Nur die Region-Auswahl-Idee übernehmen.
- `main`-Methoden `run_agents()` und `analyze_without_report()` beibehalten.
- RLP-Agent-Auswahl in die bestehende `main`-Struktur einbauen.

### `frontend/app/page.tsx` und `frontend/components/Map.tsx`

Nicht übernehmen.

Grund:

- Der Branch hat dort eine ältere Polygon-Interaktion.
- `main` hat inzwischen ein deutlich weiter entwickeltes Bayern-Flächen-UI.
- Genau dort entstehen beim Merge die größten Konflikte.

Wenn Du RLP im Frontend brauchst, reicht wahrscheinlich erst einmal:

- Coverage-Text um RLP erweitern
- optional RLP-Demopunkte
- keine Übernahme des Feature-Map-Setups

## Branch-Schwächen, Die Du Beim Porten Beseitigen Solltest

### 1. Diagnostics und echte Analyse sind inkonsistent

In `config.py` sind fast alle RLP-Quellen für Diagnostics auf `probe="get_map"` gesetzt.

Die eigentlichen RLP-Agents rufen aber weiter `GetFeatureInfo` auf. Das ist im Branch z.B. so:

- `backend/agents/rlp_flood_agent.py`
- `backend/agents/rlp_nature_agent.py`
- `backend/agents/rlp_heritage_agent.py`
- `backend/agents/rlp_land_value_agent.py`

Das ist fachlich wacklig:

- `INSPIRE` Nature ist laut Research gar nicht queryable
- `VBORIS` liefert im freien Dienst nur sehr eingeschränkte Infos
- `GDKE` und Flood liefern oft valide leere Antworten

Empfehlung:

- Diagnostics mit `GetMap` beibehalten
- echte Analyse pro Quelle neu entscheiden
- bei leeren Antworten sauber zwischen `keine Daten am Punkt` und `Service kaputt` trennen

### 2. Debug-Endpoint bricht den bestehenden Test

Im Branch werden die RLP-Quellen ungefiltert im Debug-Endpoint ergänzt. Dadurch steigt `total_sources` und `backend/tests/test_debug.py` fällt.

Wenn Du das portest, musst Du die Tests mitziehen oder RLP-Debug bewusst optional machen.

### 3. `backend/geo/wfs_client.py` ist optional

Die Datei wurde zwar neu hinzugefügt, ist für den aktuellen RLP-Pfad aber nicht zwingend.

Du kannst sie beim ersten Port wahrscheinlich ignorieren, solange Du keine echte WFS-Abfrage für GDKE oder Wasserportal einbaust.

## Minimaler Port-Plan

Wenn Du es schlank halten willst:

1. `backend/config.py`
   RLP-BBOX und `WMS_RLP_*`-Konstanten übernehmen.
2. `backend/agents/rlp_*.py`
   Dateien übernehmen und in `backend/agents/rlp_agents.py` bündeln.
3. bestehenden Orchestrator in `main` erweitern
   Region erkennen, je nach Region Agent-Liste wählen, aber `main`-Area-Flow intakt lassen.
4. `backend/main.py`
   Regionserkennung und Coverage-Meldungen ergänzen.
5. optional `backend/debug.py`
   RLP-Diagnostics nur dann ergänzen, wenn Du die Testsemantik mitziehst.

## Rohdateien Aus Dem Branch Ansehen

Wenn Du den Originalstand direkt anschauen willst:

```bash
git show origin/feature/rlp-datasources:backend/config.py
git show origin/feature/rlp-datasources:backend/main.py
git show origin/feature/rlp-datasources:backend/orchestrator.py
git show origin/feature/rlp-datasources:backend/debug.py
git show origin/feature/rlp-datasources:backend/agents/rlp_flood_agent.py
git show origin/feature/rlp-datasources:backend/agents/rlp_nature_agent.py
git show origin/feature/rlp-datasources:backend/agents/rlp_heritage_agent.py
git show origin/feature/rlp-datasources:backend/agents/rlp_land_value_agent.py
git show origin/feature/rlp-datasources:docs/rlp-services-research.md
```

## Meine Einschätzung

Der brauchbare Teil des Branches ist:

- die recherchierten RLP-Service-URLs
- die neue RLP-Agent-Struktur
- die Debug-/Probe-Erkenntnisse aus der Research-Datei

Der riskante Teil ist:

- der komplette Frontend-Pfad
- das Überschreiben des aktuellen Orchestrators
- die implizite Annahme, dass `GetFeatureInfo` für alle RLP-Quellen sinnvoll genug ist
