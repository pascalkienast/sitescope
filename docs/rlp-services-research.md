# RLP WMS Services Research Report

## Summary

| Service | Status | GetFeatureInfo | GetMap | WFS Available | Recommended Probe |
|---------|--------|----------------|--------|--------------|-------------------|
| VBORIS RLP | Working | Yes (returns boundedBy only) | Yes | Unknown | GetMap |
| GDKE Heritage | Working | Yes (empty at most points) | Yes | Yes | GetMap |
| INSPIRE Nature | Working | **No** (queryable="0") | Yes | Yes | GetMap |
| Überschwemmungsgebiete | Working | Yes (empty outside flood zones) | Yes | Yes | GetMap |
| HWGK Flood | Working | Yes (empty outside flood zones) | Yes | Yes | GetMap |

---

## 1. VBORIS RLP (Land Values)

### Official Documentation
- **Source**: BORIS.RLP - Bodenrichtwertinformationssystem Rheinland-Pfalz
- **Provider**: Oberer Gutachterausschuss für Grundstückswerte RLP

### Endpoints
```
# Via GeoPortal proxy
https://geo5.service24.rlp.de/wms/RLP_VBORISFREE2026.fcgi?

# Official GetCapabilities URL
https://www.geoportal.rlp.de/mapbender/php/wms.php?inspire=1&layer_id=32937&withChilds=1&REQUEST=GetCapabilities&SERVICE=WMS
```

### Service Details
- **WMS Version**: 1.1.1
- **CRS**: EPSG:25832 (ETRS89/UTM Zone 32N)
- **Layers**:
  - `Bodenrichtwerte_Basis_RLP` - Basisdienst (free)
  - `RLP_1` - Basisdienst bebaut
  - `RLP_0` - Basisdienst landwirtschaftlich
- **GetFeatureInfo**: Returns polygon bounding box, NOT attribute values
- **Note**: GetFeatureInfo only returns `<boundedBy>`, actual Bodenrichtwert values require Premiumdienst

### Issue
GetFeatureInfo returns `<msGMLOutput>` with only `<boundedBy>` element - no actual land value data in Basisdienst. The actual Bodenrichtwert (BRW) values are in the Premiumdienst which requires payment.

### Recommendation
- Use `probe: "get_map"` for diagnostics
- Don't rely on GetFeatureInfo for actual BRW data in Basisdienst

---

## 2. GDKE RLP (Heritage/Monuments)

### Official Documentation
- **Source**: Generaldirektion Kulturelles Erbe Rheinland-Pfalz
- **WFS Documentation**: https://www.geoportal.rlp.de/registry/wfs/665?VERSION=1.1.0

### Endpoints
```
# GetCapabilities
https://www.geoportal.rlp.de/mapbender/php/wms.php?layer_id=54697&REQUEST=GetCapabilities&VERSION=1.1.1&SERVICE=WMS&withChilds=1

# Request endpoint (as shown in capabilities)
https://www.geoportal.rlp.de/owsproxy/00000000000000000000000000000000/9c9d7fe2c25527a5cb22cf9ca2266d26?

# WFS endpoint
https://www.geoportal.rlp.de/registry/wfs/665?VERSION=1.1.0
```

### Service Details
- **WMS Version**: 1.1.1
- **CRS**: EPSG:4326, EPSG:25832, EPSG:31466, EPSG:31467, EPSG:4258, EPSG:3857, EPSG:4647
- **Layers** (all queryable):
  - `pgis_landesdenkmalpflege_sld` - Denkmalliste (main layer)
  - `denkmalzonen` - Denkmalzonen (heritage zones)
  - `bga` - Bauliche Gesamtanlagen (building ensembles)
  - `gruenflaechen` - Grünflächen (green spaces)
  - `wasserflaechen` - Wasserflächen (water areas)
  - `edm_flaechen` - Einzeldenkmäler Flächen (monument areas)
  - `edm_linien` - Einzeldenkmäler Linien (monument lines)
  - `edm_punkte` - Einzeldenkmäler Punkte (monument points)
- **GetFeatureInfo**: Supports text/plain, text/html, application/vnd.ogc.gml
- **STYLES**: Required parameter

### Issue
Service returns empty responses at most test points because monuments are specific locations, not blanket coverage.

### Recommendation
- Use `probe: "get_map"` for diagnostics
- For actual analysis, test multiple layers since monuments may only appear in specific ones

---

## 3. INSPIRE Schutzgebiete (Nature)

### Official Documentation
- **Source**: Ministerium für Klimaschutz, Umwelt, Energie und Mobilität RLP
- **Metadata**: https://www.portalu.rlp.de/trefferanzeige?docuuid=E2955909-B775-4EF9-896C-3C4907D7845F

### Endpoints
```
# Original WMS URL
https://inspire.naturschutz.rlp.de/cgi-bin/wfs/ps_wms?language=ger&

# Via GeoPortal proxy
https://www.geoportal.rlp.de/mapbender/php/wms.php?inspire=1&layer_id=81950&withChilds=1&REQUEST=GetCapabilities&SERVICE=WMS
```

### Service Details
- **WMS Version**: 1.1.1
- **CRS**: EPSG:4326
- **Layers** (ALL NOT queryable):
  - `PS.ProtectedSite` - Root layer
  - `PS.ProtectedSitesNatureConservation` - Nature conservation
  - `PS.ProtectedSitesNationalPark` - National parks
  - `PS.ProtectedSitesBiosphereReserve` - Biosphere reserves
  - `PS.ProtectedSitesSpecialAreaOfConservation` - FFH/SAC
- **GetFeatureInfo**: **NOT SUPPORTED** - queryable="0" on all layers
- **GetMap**: Supported

### Issue
All layers have `queryable="0"` - GetFeatureInfo is not supported. Returns ServiceException if attempted.

### Recommendation
- **Must use** `probe: "get_map"` for diagnostics
- Can only check if the service is reachable, not query feature data

---

## 4. Überschwemmungsgebiete (Flood Zones)

### Official Documentation
- **Source**: Wasserwirtschaftsverwaltung Rheinland-Pfalz
- **Portal**: https://wasserportal.rlp-umwelt.de/kartendienste

### Endpoints
```
# WMS
https://geodienste-wasser.rlp-umwelt.de/maps/uesg/wms?

# WFS (unchanged after URL migration)
https://geodienste-wasser.rlp-umwelt.de/geoserver/uesg/wfs?
```

### Service Details
- **WMS Version**: 1.1.1 / 1.3.0
- **CRS**: EPSG:4326, EPSG:25832, EPSG:31466, EPSG:31467, EPSG:3857, EPSG:4258
- **Layers** (all queryable):
  - `uesg_gesetzlich` - Gesetzlich festgesetzte Überschwemmungsgebiete
  - `risikogebiete_ausserhalb_uesg` - Risikogebiete außerhalb ÜSG
  - `RISIKOGEBIETE_AUSSERHALB_UESG_WEITERE` - Weitere überschwemmungsgefährdete Gebiete
- **GetFeatureInfo**: Supported (text/plain, text/html, text/xml)
- **WFS**: Available with GetFeature, DescribeFeatureType

### Issue
GetFeatureInfo returns empty `<wfs:FeatureCollection><gml:boundedBy><gml:null>unknown</gml:null></gml:boundedBy></wfs:FeatureCollection>` when no flood zone exists at the query point. This is **valid behavior** - not all points are in flood zones.

### Recommendation
- Use `probe: "get_map"` for diagnostics
- For actual analysis, expect empty responses outside flood zones

---

## 5. Hochwassergefahrenkarte (Flood Hazard Map)

### Official Documentation
- **Source**: Wasserwirtschaftsverwaltung Rheinland-Pfalz
- **Portal**: https://wasserportal.rlp-umwelt.de/kartendienste

### Endpoints
```
# WMS
https://geodienste-wasser.rlp-umwelt.de/maps/HWGK/wms?

# Via GeoPortal
https://www.geoportal.rlp.de/mapbender/php/wms.php?inspire=1&layer_id=73107&withChilds=1&REQUEST=GetCapabilities&SERVICE=WMS
```

### Service Details
- **WMS Version**: 1.1.1 / 1.3.0
- **CRS**: EPSG:4326, EPSG:25832, EPSG:31466, EPSG:31467, EPSG:3857, EPSG:4258
- **Layers** (all queryable):
  - `HWMR_RISIKO_2024` - Risikogewässer HWRM-RL
  - `Ueberflutungsflaechen_HQ_010` - HQ10 flooding areas
  - `Ueberflutungsflaechen_HQ_100` - HQ100 flooding areas
  - `Ueberflutungsflaechen_HQ_extrem` - HQ extreme flooding areas
  - `HQ10_akt_Land_utm32` - Wassertiefen HQ10
  - `HQ100_akt_Land_utm32` - Wassertiefen HQ100
  - `HQext_akt_Land_utm32` - Wassertiefen HQ extrem
  - `HQ10_pot_Land_utm32` - Wassertiefen HQ10 potentiell
- **GetFeatureInfo**: Supported (text/plain, text/html, text/xml)
- **License**: CC-BY-4.0

### Issue
Same as Überschwemmungsgebiete - returns empty outside flood zones.

### Recommendation
- Use `probe: "get_map"` for diagnostics
- For analysis, expect empty responses outside flood zones

---

## Recommendations for Implementation

### 1. All services should use `probe: "get_map"` for diagnostics
The GetFeatureInfo approach doesn't work well for these services because:
- VBORIS returns only boundedBy (no BRW values in Basisdienst)
- GDKE returns empty at non-monument locations
- INSPIRE doesn't support GetFeatureInfo
- Flood services return empty outside flood zones

### 2. For actual analysis (when user clicks in RLP), use GetFeatureInfo but handle empty responses gracefully
- If empty, show "No [category] data at this location" instead of "Service failed"

### 3. Use official GeoPortal proxy URLs when available
Some services have official GetCapabilities URLs through GeoPortal that may be more reliable.

### 4. Consider WFS for GDKE Heritage
The WFS endpoint may provide better results than WMS GetFeatureInfo:
```
https://www.geoportal.rlp.de/registry/wfs/665?VERSION=1.1.0
```
