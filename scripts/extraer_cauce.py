# -*- coding: utf-8 -*-
"""Extrae la red de drenaje y el cauce principal del río Amaime desde la acumulación
de flujo D8, los vectoriza y exporta GeoJSON (EPSG:4326) para el mapa Leaflet.
Solo LEE de Salida/ (archivos estables); escribe temporales en el scratchpad."""
import json
from pathlib import Path
import numpy as np
import rasterio
import geopandas as gpd
import whitebox

SAL = Path(r"D:/Diego Angrino Chiran/Documentos/Cenicaña/SOLIX/RUSLE_Amaime/Salida")
RAST = SAL / "rasters"; TAB = SAL / "tablas"; MAP = SAL / "mapas"; FIG = SAL / "figuras"
for _d in (RAST, TAB, MAP, FIG): _d.mkdir(parents=True, exist_ok=True)
SP = Path(r"C:/Temporal/claude/d--Diego-Angrino-Chiran-Documentos-Cenica-a-SOLIX-RUSLE-Amaime-Script/f7e5098e-49e8-42ce-843e-44fb9c824813/scratchpad")
TMP = SP / "_cauce_tmp"
TMP.mkdir(exist_ok=True)

FACC = RAST / "Flow_Accumulation.tif"
D8 = RAST / "D8_Pointer.tif"

with rasterio.open(FACC) as s:
    facc = s.read(1).astype("float64")
    facc = np.where(facc == s.nodata, np.nan, facc)
pos = facc[np.isfinite(facc) & (facc > 0)]
print("Flow accum: max =", int(np.nanmax(pos)), " p99.5 =", int(np.nanpercentile(pos, 99.5)),
      " p99.9 =", int(np.nanpercentile(pos, 99.9)))

wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(str(TMP))
wbt.verbose = False

# dos niveles: red de drenaje (tributarios) y cauce principal
NIVELES = {
    "red_drenaje": 800,        # celdas: red densa
    "cauce_principal": 25000,  # celdas: solo el eje del Amaime y grandes tributarios
}

out_geojson = {}
for nombre, thr in NIVELES.items():
    strm = TMP / f"streams_{nombre}.tif"
    shp = TMP / f"streams_{nombre}.shp"
    wbt.extract_streams(str(FACC), str(strm), threshold=thr)
    wbt.raster_streams_to_vector(str(strm), str(D8), str(shp))
    g = gpd.read_file(shp)
    if g.crs is None:
        g = g.set_crs("EPSG:3115")
    g = g.to_crs("EPSG:4326")
    # simplificar un poco para aligerar el GeoJSON
    g["geometry"] = g.geometry.simplify(0.0003)
    feats = []
    for geom in g.geometry:
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "LineString":
            feats.append([[round(y, 5), round(x, 5)] for x, y in geom.coords])
        elif geom.geom_type == "MultiLineString":
            for ln in geom.geoms:
                feats.append([[round(y, 5), round(x, 5)] for x, y in ln.coords])
    out_geojson[nombre] = feats
    n_pts = sum(len(f) for f in feats)
    print(f"  {nombre} (umbral {thr}): {len(feats)} líneas, {n_pts} vértices")

(SP / "cauce_amaime.json").write_text(json.dumps(out_geojson), encoding="utf-8")
kb = len((SP / "cauce_amaime.json").read_text(encoding="utf-8")) / 1024
print(f"\ncauce_amaime.json escrito ({kb:.0f} KB)")
