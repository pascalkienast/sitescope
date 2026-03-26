# SiteScope — Geo API Source Reference

Quick reference for all WMS/WFS services and external APIs used.

## 🌊 Flood & Water (Bayern LfU)

### Überschwemmungsgebiete (Flood Zones)
- **URL:** `https://www.lfu.bayern.de/gdi/wms/wasser/ueberschwemmungsgebiete`
- **Layers:** `hwgf_uesg_hq100`, `hwgf_uesg_hqextrem`, `vwgf_uesg_hq100`, `vwgf_uesg_hqextrem`
- **CRS:** EPSG:25832
- **Info Format:** text/plain
- **Portal:** [LfU Hochwasser](https://www.lfu.bayern.de/wasser/hw_risikomanagement_umsetzung/index.htm)

### Wassertiefen (Water Depths)
- **URL:** `https://www.lfu.bayern.de/gdi/wms/wasser/wassertiefen`
- **Layers:** `wt_hq100`, `wt_hqextrem`
- **Portal:** [LfU Hochwasser](https://www.lfu.bayern.de/wasser/hw_risikomanagement_umsetzung/index.htm)

### Oberflächenabfluss (Surface Runoff)
- **URL:** `https://www.lfu.bayern.de/gdi/wms/wasser/oberflaechenabfluss`
- **Layers:** `oa_starkregen_selten`, `oa_starkregen_extrem`

## 🌿 Nature & Environment (Bayern LfU)

### Schutzgebiete (Protected Areas)
- **URL:** `https://www.lfu.bayern.de/gdi/wms/natur/schutzgebiete`
- **Layers:** `naturschutzgebiet`, `landschaftsschutzgebiet`, `natura2000_ffh`, `natura2000_spa`
- **Portal:** [LfU Naturschutz](https://www.lfu.bayern.de/natur/index.htm)

### Geotope
- **URL:** `https://www.lfu.bayern.de/gdi/wms/geologie/geotope`
- **Layers:** `geotopflaeche`, `geotoppunkt`

### Trinkwasserschutzgebiete (Drinking Water Protection)
- **URL:** `https://www.lfu.bayern.de/gdi/wms/wasser/trinkwasserschutzgebiete`
- **Layers:** `trinkwasserschutzgebiet`

### Bodenschätzung (Soil Assessment)
- **URL:** `https://www.lfu.bayern.de/gdi/wms/boden/bodenschaetzung`
- **Layers:** `bodenschaetzung`

## 🏛️ Heritage / Monuments (BLfD)

### Denkmäler (Monuments)
- **URL:** `https://geoservices.bayern.de/od/wms/gdi/v1/denkmal`
- **Layers:** `einzeldenkmalO`, `bodendenkmalO`, `bauensembleO`, `landschaftsdenkmalO`
- **Portal:** [BLfD](https://www.blfd.bayern.de/)

## 📐 Zoning / Climate (External)

### Open-Meteo (Climate Data)
- **URL:** `https://archive-api.open-meteo.com/v1/archive`
- **Type:** REST API (JSON)
- **Auth:** None required
- **Used for:** Annual precipitation, max daily rainfall, snowfall
- **Docs:** [Open-Meteo API](https://open-meteo.com/en/docs)

## ⚡ Infrastructure (External)

### Open Topo Data (Elevation)
- **URL:** `https://api.opentopodata.org/v1/eudem25m`
- **Type:** REST API (JSON)
- **Auth:** None required
- **Resolution:** 25m (EU-DEM)
- **Docs:** [OpenTopoData](https://www.opentopodata.org/)

## Technical Notes

### Coordinate Systems
- **Frontend map:** WGS84 (EPSG:4326)
- **WMS queries:** EPSG:25832 (ETRS89 / UTM Zone 32N) — standard for German geo services
- **Transformation:** Done in `geo/transforms.py` via pyproj

### WMS Request Pattern
```
GET {base_url}?
  SERVICE=WMS&
  VERSION=1.1.1&
  REQUEST=GetFeatureInfo&
  LAYERS={layer}&
  QUERY_LAYERS={layer}&
  SRS=EPSG:25832&
  BBOX={min_x},{min_y},{max_x},{max_y}&
  WIDTH=256&HEIGHT=256&
  X=128&Y=128&
  INFO_FORMAT=text/plain&
  FEATURE_COUNT=50
```

### Common Issues
- Some LfU services are slow (5-10s response time) — use adequate timeouts
- Heritage WMS may return `text/html` instead of `text/plain` for some layers
- BBOX must be in the same CRS as the SRS parameter
- Some layers return empty results even within visible areas if zoom is wrong — buffer of 50m works well
