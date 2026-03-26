# SiteScope: Alle 24 Datenquellen erklaert

Diese Datei beschreibt die 24 Quellen, die aktuell in `/api/debug/sources` auftauchen.

Wichtig:

- Die Liste ist am aktuellen Code in `backend/config.py` und `backend/debug.py` ausgerichtet.
- Die Diagnostics pruefen pro WMS-Service nur eine repraesentative Layer-Abfrage, nicht alle Layer.
- Viele Bayern-LfU-WMS-Services liefern `GetFeatureInfo` absichtlich als HTML zurueck. Das ist fuer diese Services normal und wird im Analysepfad geparst.
- Von den 24 Quellen sind 21 fachliche Karten-/Datenquellen und 3 technische API-Quellen.

## Zaehllogik der 24 Quellen

| Block | Anzahl |
| --- | ---: |
| Flood WMS | 4 |
| Flood Monitoring-only WMS | 1 |
| Nature WMS | 6 |
| Heritage WMS | 1 |
| Zoning WMS | 2 |
| Infrastructure WMS | 7 |
| Externe APIs | 3 |
| Summe | 24 |

## Kurzuebersicht

| Nr. | Quelle | Typ | Verwendet von | Im Analyse-Run aktiv |
| --- | --- | --- | --- | --- |
| 1 | Ueberschwemmungsgebiete | WMS | FloodAgent | ja |
| 2 | Wassertiefen bei Hochwasser | WMS | FloodAgent | ja |
| 3 | Oberflaechenabfluss bei Starkregen | WMS | FloodAgent | ja |
| 4 | Lawinenkataster | WMS | FloodAgent | ja |
| 5 | Hohe Grundwasserstaende | WMS/GetMap | nur Diagnostics | nein |
| 6 | Schutzgebiete | WMS | NatureAgent | ja |
| 7 | Geotope | WMS | NatureAgent | ja |
| 8 | Trink- und Heilquellenschutzgebiete | WMS | NatureAgent | ja |
| 9 | Bodenfunktionskarte BFK25 | WMS | NatureAgent | ja |
| 10 | Biotopkartierung | WMS | NatureAgent | ja |
| 11 | Oekoflaechenkataster | WMS | NatureAgent | ja |
| 12 | BLfD Denkmal | WMS/GML | HeritageAgent | ja |
| 13 | Laermkarten Hauptverkehrsstrassen | WMS | ZoningAgent | ja |
| 14 | Rohstoff-Gewinnungsstellen | WMS | ZoningAgent | ja |
| 15 | Georisiken | WMS | InfraAgent | ja |
| 16 | Ingenieurgeologie dIGK25 | WMS | InfraAgent | ja |
| 17 | Geologie dGK25 | WMS | InfraAgent | ja |
| 18 | Hydrogeologie dHK100 | WMS | InfraAgent | ja |
| 19 | Bodenuebersichtskarte BUEK200 | WMS | InfraAgent | ja |
| 20 | Uebersichtsbodenkarte UEBK25 | WMS | InfraAgent | ja |
| 21 | Energie-Atlas Geothermie | WMS | InfraAgent | ja |
| 22 | Open-Meteo Archive | REST/JSON | ZoningAgent | ja |
| 23 | OpenTopoData EU-DEM 25m | REST/JSON | InfraAgent | ja |
| 24 | OpenRouter | REST/JSON | ReportGenerator, Diagnostics | ja, wenn API-Key gesetzt |

## Antwortformate

### WMS-Quellen

SiteScope nutzt bei den meisten Bayern-LfU-WMS-Diensten:

- `REQUEST=GetFeatureInfo`
- CRS `EPSG:25832`
- `INFO_FORMAT=text/html`

Der Grund ist pragmatisch: Mehrere ArcGIS-WMS-Endpoints liefern mit `text/plain` fehlerhafte oder instabile Antworten, mit `text/html` aber sauber. Die HTML-Antwort wird in `backend/geo/parsers.py` in strukturierte Key-Value-Daten zerlegt.

Ausnahme:

- Die Denkmal-Quelle nutzt `application/vnd.ogc.gml`.
- Die Monitoring-only-Grundwasserquelle wird im Debug per `GetMap` geprueft, weil sie nicht sinnvoll per `GetFeatureInfo` abgefragt wird.

### REST-Quellen

- Open-Meteo und OpenTopoData liefern JSON.
- OpenRouter liefert JSON fuer `/models` und `/chat/completions`.

## Die 24 Quellen im Detail

## 1. Ueberschwemmungsgebiete

- URL: `https://www.lfu.bayern.de/gdi/wms/wasser/ueberschwemmungsgebiete`
- Typ: WMS `GetFeatureInfo`
- Agent: FloodAgent
- Layer: `hwgf_hqhaeufig`, `hwgf_hq100`, `hwgf_hqextrem`, `hwgg_hq100`
- Fachliche Bedeutung: Gesetzlich oder fachlich kartierte Flutbereiche.
- Interpretation im Code:
  - `hwgf_hqhaeufig` -> HIGH
  - `hwgf_hq100` -> HIGH
  - `hwgf_hqextrem` -> MEDIUM
  - `hwgg_hq100` -> MEDIUM
- Typischer Nutzen: Erste Aussage, ob ein Standort in einem relevanten Flutbereich liegt.

## 2. Wassertiefen bei Hochwasser

- URL: `https://www.lfu.bayern.de/gdi/wms/wasser/wassertiefen`
- Typ: WMS `GetFeatureInfo`
- Agent: FloodAgent
- Layer: `wt_hqhaeufig`, `wt_hq100`, `wt_hqextrem`, `wt_hwgg_hq100`
- Fachliche Bedeutung: Erwartete Ueberflutungstiefen fuer verschiedene Szenarien.
- Interpretation im Code:
  - `wt_hqhaeufig` -> HIGH
  - `wt_hq100` -> MEDIUM oder HIGH, je nach erkannter Tiefe
  - `wt_hqextrem` -> MEDIUM
  - `wt_hwgg_hq100` -> MEDIUM
- Typischer Nutzen: Wichtig fuer Keller, Gebaeudeschutz und Schadenpotenzial.

## 3. Oberflaechenabfluss bei Starkregen

- URL: `https://www.lfu.bayern.de/gdi/wms/wasser/oberflaechenabfluss`
- Typ: WMS `GetFeatureInfo`
- Agent: FloodAgent
- Layer: `senken_aufstau`, `fliesswege`
- Fachliche Bedeutung: Hinweise auf Stau- und Fliesspfade bei Starkregen.
- Interpretation im Code:
  - `senken_aufstau` -> MEDIUM
  - `fliesswege` -> MEDIUM
- Typischer Nutzen: Ergaenzt Fluss-/Auenhochwasser um pluviale Risiken.

## 4. Lawinenkataster

- URL: `https://www.lfu.bayern.de/gdi/wms/wasser/lawinenkataster`
- Typ: WMS `GetFeatureInfo`
- Agent: FloodAgent
- Layer: `ueberwachte_lawinenstriche`, `nicht_ueberwachte_lawinenstriche`
- Fachliche Bedeutung: Kartierte Lawinenstriche im alpinen Raum.
- Interpretation im Code:
  - ueberwacht -> HIGH
  - nicht ueberwacht -> MEDIUM
- Typischer Nutzen: Relevant fuer Standorte im suedlichen Bayern.

## 5. Hohe Grundwasserstaende

- URL: `https://www.lfu.bayern.de/gdi/wms/wasser/hohegrundwasserstaende`
- Typ: WMS `GetMap` im Debug
- Agent: keiner
- Layer: `hwk_hgw`
- Fachliche Bedeutung: Quelle fuer hohe Grundwasserstaende.
- Nutzung im Produkt:
  - aktuell nur in den Diagnostics
  - nicht Teil des eigentlichen Analyse-Runs
- Besonderheit: Wird nicht per `GetFeatureInfo`, sondern nur per `GetMap` auf Erreichbarkeit geprueft.

## 6. Schutzgebiete

- URL: `https://www.lfu.bayern.de/gdi/wms/natur/schutzgebiete`
- Typ: WMS `GetFeatureInfo`
- Agent: NatureAgent
- Layer: `naturschutzgebiet`, `landschaftsschutzgebiet`, `nationalpark`, `biosphaerenreservat`, `fauna_flora_habitat_gebiet`, `vogelschutzgebiet`
- Fachliche Bedeutung: Uebergreifende Schutzkulissen aus dem Naturschutz.
- Interpretation im Code:
  - `naturschutzgebiet` -> HIGH
  - `landschaftsschutzgebiet` -> MEDIUM
  - `fauna_flora_habitat_gebiet` -> HIGH
  - `vogelschutzgebiet` -> HIGH
  - `nationalpark` -> aktuell generisch MEDIUM
  - `biosphaerenreservat` -> aktuell generisch MEDIUM
- Typischer Nutzen: Fruehindikator fuer starke naturschutzrechtliche Restriktionen.

## 7. Geotope

- URL: `https://www.lfu.bayern.de/gdi/wms/geologie/geotope`
- Typ: WMS `GetFeatureInfo`
- Agent: NatureAgent
- Layer: `geotoplage`
- Fachliche Bedeutung: Schutz- oder Hinweisflaechen mit geologisch besonderer Bedeutung.
- Interpretation im Code: MEDIUM
- Typischer Nutzen: Kann Erdarbeiten und Eingriffe erschweren.

## 8. Trink- und Heilquellenschutzgebiete

- URL: `https://www.lfu.bayern.de/gdi/wms/wasser/wsg`
- Typ: WMS `GetFeatureInfo`
- Agent: NatureAgent
- Layer: `twsg`, `hqsg`
- Fachliche Bedeutung: Wasserrechtlich sensible Schutzzonen.
- Interpretation im Code:
  - `twsg` -> HIGH
  - `hqsg` -> HIGH
- Typischer Nutzen: Relevant fuer Eingriffe in Boden, Entwaesserung und Stoffeintrag.

## 9. Bodenfunktionskarte BFK25

- URL: `https://www.lfu.bayern.de/gdi/wms/boden/bfk25`
- Typ: WMS `GetFeatureInfo`
- Agent: NatureAgent
- Layer: `bfk25_nat_ertragsfaehigkeit_gesamt`
- Fachliche Bedeutung: Natuerliche Ertragsfaehigkeit des Bodens.
- Interpretation im Code: LOW
- Typischer Nutzen: Mehr Kontext als harte Restriktionsquelle.

## 10. Biotopkartierung

- URL: `https://www.lfu.bayern.de/gdi/wms/natur/biotopkartierung`
- Typ: WMS `GetFeatureInfo`
- Agent: NatureAgent
- Layer: `bio_abk`, `bio_sbk`, `bio_fbk`
- Fachliche Bedeutung: Kartierte geschuetzte oder oekologisch relevante Biotope.
- Interpretation im Code:
  - `bio_abk` -> HIGH
  - `bio_sbk` -> HIGH
  - `bio_fbk` -> HIGH
- Typischer Nutzen: Einer der staerksten naturschutzfachlichen Red-Flag-Indikatoren.

## 11. Oekoflaechenkataster

- URL: `https://www.lfu.bayern.de/gdi/wms/natur/oefk`
- Typ: WMS `GetFeatureInfo`
- Agent: NatureAgent
- Layer: `oefk_ankauf`, `oefk_ae`, `oefk_flurb`, `oefk_oek`
- Fachliche Bedeutung: Ausgleichs-, Ersatz- oder Oekokonto-Flaechen.
- Interpretation im Code: alle vier Layer -> MEDIUM
- Typischer Nutzen: Wichtig fuer Flaechen mit naturschutzrechtlicher Bindung oder Kompensationsfunktion.

## 12. BLfD Denkmal

- URL: `https://geoservices.bayern.de/od/wms/gdi/v1/denkmal`
- Typ: WMS `GetFeatureInfo` mit GML
- Agent: HeritageAgent
- Layer: `einzeldenkmalO`, `bodendenkmalO`, `bauensembleO`, `landschaftsdenkmalO`
- Fachliche Bedeutung: Denkmalrechtliche Schutzobjekte und Ensembles.
- Interpretation im Code:
  - `einzeldenkmalO` -> HIGH
  - `bodendenkmalO` -> HIGH
  - `bauensembleO` -> MEDIUM
  - `landschaftsdenkmalO` -> MEDIUM
- Typischer Nutzen: Relevanz fuer Genehmigungen, Gestaltung, Erdarbeiten und Umgebungsvertraeglichkeit.

## 13. Laermkarten Hauptverkehrsstrassen

- URL: `https://www.lfu.bayern.de/gdi/wms/laerm/hauptverkehrsstrassen`
- Typ: WMS `GetFeatureInfo`
- Agent: ZoningAgent
- Layer: `mroadbylden2022`, `mroadbyln2022`
- Fachliche Bedeutung: Offizielle Laermkartierung fuer grosse Strassen.
- Interpretation im Code:
  - `mroadbylden2022` -> HIGH ab 75 dB(A), MEDIUM ab 65 dB(A), sonst LOW
  - `mroadbyln2022` -> HIGH ab 65 dB(A), MEDIUM ab 55 dB(A), sonst LOW
- Typischer Nutzen: Frueher Hinweis auf Wohn-/Nutzungsqualitaet und Schallschutzbedarf.

## 14. Rohstoff-Gewinnungsstellen

- URL: `https://www.lfu.bayern.de/gdi/wms/geologie/rohstoff_gewinnungsstellen`
- Typ: WMS `GetFeatureInfo`
- Agent: ZoningAgent
- Layer: `gf_webgis_umriss_aktiv`, `gf_webgis_umriss_inaktiv`
- Fachliche Bedeutung: Aktive oder ehemalige Rohstoffgewinnungsflaechen.
- Interpretation im Code:
  - aktiv -> MEDIUM
  - inaktiv -> LOW
- Typischer Nutzen: Hinweise auf Vorbelastung, Nutzungskonflikte oder geotechnische Besonderheiten.

## 15. Georisiken

- URL: `https://www.lfu.bayern.de/gdi/wms/geologie/georisiken`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `ghk_senkungsgebiete`, `ghk_dol_erdf`, `ghk_hang_extrem`, `ghk_hang`, `ghk_rutschanf`, `ghk_tief_rutsch`, `ghk_sturz_o_wald`
- Fachliche Bedeutung: Geologische Gefahren wie Setzung, Dolinen, Rutschung oder Steinschlag.
- Interpretation im Code:
  - mehrere Layer -> HIGH
  - `ghk_hang` und `ghk_rutschanf` -> MEDIUM
- Typischer Nutzen: Einer der wichtigsten Geo-Risk-Bloecke fuer Baugrund und Hangsicherheit.

## 16. Ingenieurgeologie dIGK25

- URL: `https://www.lfu.bayern.de/gdi/wms/geologie/digk25`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `baugrund_digk25`
- Fachliche Bedeutung: Ingenieurgeologische Einordnung des Baugrunds.
- Interpretation im Code: LOW
- Typischer Nutzen: Mehr Kontext fuer Gruendung und Baugrundbeurteilung als unmittelbare rote Flagge.

## 17. Geologie dGK25

- URL: `https://www.lfu.bayern.de/gdi/wms/geologie/dgk25`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `geoleinheit_dgk25`, `strukturln_dgk25`
- Fachliche Bedeutung: Geologische Einheiten und Strukturinformationen.
- Interpretation im Code:
  - `geoleinheit_dgk25` -> LOW
  - `strukturln_dgk25` -> MEDIUM
- Typischer Nutzen: Liefert geologischen Kontext und moegliche Strukturhinweise.

## 18. Hydrogeologie dHK100

- URL: `https://www.lfu.bayern.de/gdi/wms/geologie/hk100`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `hk100_klass`, `hk100_deck`, `hk100_stockw`
- Fachliche Bedeutung: Grundwasser- und Deckschichtkontext.
- Interpretation im Code: alle drei Layer -> LOW
- Typischer Nutzen: Hintergrundwissen zu hydrogeologischen Verhaeltnissen.

## 19. Bodenuebersichtskarte BUEK200

- URL: `https://www.lfu.bayern.de/gdi/wms/boden/buek200by`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `buek200`
- Fachliche Bedeutung: Regionale Uebersicht ueber Bodentypen.
- Interpretation im Code: LOW
- Typischer Nutzen: Grober Boden-Kontext, eher fachliche Einordnung als Red Flag.

## 20. Uebersichtsbodenkarte UEBK25

- URL: `https://www.lfu.bayern.de/gdi/wms/boden/uebk25`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `kartiereinheiten_uebk25`
- Fachliche Bedeutung: Detailliertere Bodenkartierung.
- Interpretation im Code: LOW
- Typischer Nutzen: Hilfreich fuer Bodencharakterisierung im Standortkontext.

## 21. Energie-Atlas Geothermie

- URL: `https://www.lfu.bayern.de/gdi/wms/energieatlas/geothermie`
- Typ: WMS `GetFeatureInfo`
- Agent: InfraAgent
- Layer: `gwwp_entzugsleistung_kw_100m`, `ews_entzugsleistung_kw`, `ewk_hk_entzugsleistung_wm2`
- Fachliche Bedeutung: Potenziale fuer verschiedene geothermische Nutzungsformen.
- Interpretation im Code: alle drei Layer -> LOW
- Typischer Nutzen: Aktuell eher Opportunity-/Kontextdaten als Risikotreiber.

## 22. Open-Meteo Archive

- URL: `https://archive-api.open-meteo.com/v1/archive`
- Typ: REST/JSON
- Agent: ZoningAgent
- Verwendete Daten: Tageswerte fuer Niederschlag, Schneefall und Temperatur fuer das Jahr 2023
- Fachliche Bedeutung: Einfacher Klima-Kontext fuer den Standort.
- Interpretation im Code:
  - Standard -> LOW
  - max. Tagesniederschlag > 50 mm -> MEDIUM
  - max. Tagesniederschlag > 80 mm -> HIGH
- Typischer Nutzen: Nur grober Kontext, kein amtliches Gefahrenmodell.

## 23. OpenTopoData EU-DEM 25m

- URL: `https://api.opentopodata.org/v1/eudem25m`
- Typ: REST/JSON
- Agent: InfraAgent
- Verwendete Daten: Hoehe ueber Meeresspiegel
- Fachliche Bedeutung: Einfache topographische Kontextinformation.
- Interpretation im Code:
  - meist LOW
  - unter 200 m bleibt LOW, aber mit Hinweis auf tiefliegende Lage
  - ueber 1000 m -> MEDIUM
- Typischer Nutzen: Grober Lagekontext fuer Entwaesserung, Schnee und Erschliessung.

## 24. OpenRouter

- URL-Basis: `https://openrouter.ai/api/v1`
- Typ: REST/JSON
- Verwendet von:
  - Diagnostics -> `GET /models`
  - Analysepfad -> `POST /chat/completions`
- Fachliche Bedeutung: Keine Geodatenquelle, sondern die einzige LLM-Quelle im System.
- Rolle im Produkt:
  - aggregiert alle Agent-Ergebnisse
  - schreibt Executive Summary
  - bestimmt die Gesamt-Risikostufe
  - erzeugt Key Red Flags und Handlungsempfehlungen
- Wichtig: Es gibt genau einen LLM-Call pro Analyse-Run, nicht pro Agent.

## Welche dieser Quellen erzeugen wirklich Red Flags?

Die staerksten Red-Flag-Quellen im aktuellen Code sind typischerweise:

- Ueberschwemmungsgebiete
- Wassertiefen bei Hochwasser
- Schutzgebiete
- Biotopkartierung
- Trink- und Heilquellenschutzgebiete
- BLfD Denkmal
- Laermkarten
- Georisiken

Kontext- oder eher schwach gewichtete Quellen sind eher:

- Bodenfunktionskarte
- dIGK25
- dGK25 Geologieeinheit
- dHK100
- BUEK200
- UEBK25
- Geothermie
- Open-Meteo
- OpenTopoData

## Was die Diagnostics-Seite wirklich prueft

Die Diagnostics beantworten primär:

- Ist der Endpoint erreichbar?
- Antwortet `GetCapabilities` sauber?
- Kommt auf eine repraesentative Datenabfrage etwas technisch gueltiges zurueck?

Die Diagnostics beantworten nicht vollstaendig:

- Ob jede einzelne Layer im produktiven Analyse-Run korrekte Fachdaten liefert
- Ob die Interpretation fachlich immer optimal ist
- Ob ein Standort inhaltlich "keine Daten" oder "kein Risiko" bedeutet

## Verwandte Dateien

- `backend/config.py`: Quellkonfiguration
- `backend/debug.py`: Health-/Diagnostics-Checks
- `backend/geo/wms_client.py`: WMS-Requests
- `backend/geo/parsers.py`: HTML-, Text- und GML-Parser
- `backend/agents/`: Fachliche Interpretation pro Agent
