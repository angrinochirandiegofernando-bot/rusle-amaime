# -*- coding: utf-8 -*-
"""Cuenca del río Amaime + red hídrica desde HydroSHEDS (Earth Engine):
- HydroBASINS -> polígono de la cuenca que contiene los 117 puntos (llega hasta el Cauca)
- HydroSHEDS Free-Flowing Rivers -> cauce del Amaime (dentro de la cuenca) y río Cauca.
Exporta cuenca_amaime.json (EPSG:4326) para el mapa Leaflet.
"""
import json
from pathlib import Path
import pandas as pd
import geopandas as gpd
import shapely.geometry as sg
import ee

SP = Path(r"C:/Temporal/claude/d--Diego-Angrino-Chiran-Documentos-Cenica-a-SOLIX-RUSLE-Amaime-Script/f7e5098e-49e8-42ce-843e-44fb9c824813/scratchpad")
ENT = Path(r"D:/Diego Angrino Chiran/Documentos/Cenicaña/SOLIX/RUSLE_Amaime/Entrada")

ee.Initialize(project="ee-pracagro2")
print("EE OK")

df = pd.read_excel(ENT / "Cuenca amaime.xlsx")
pts = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r.LONG), float(r.LAT)]))
                            for r in df.itertuples()])
region = ee.Geometry.Rectangle([float(df.LONG.min()) - 0.35, float(df.LAT.min()) - 0.2,
                                float(df.LONG.max()) + 0.35, float(df.LAT.max()) + 0.2])


def latlon_lines(fc):
    """FeatureCollection de líneas -> lista de polilíneas [[lat,lon],...]."""
    gj = fc.getInfo()
    out = []
    for f in gj["features"]:
        g = f["geometry"]
        if g["type"] == "LineString":
            out.append([[round(c[1], 5), round(c[0], 5)] for c in g["coordinates"]])
        elif g["type"] == "MultiLineString":
            for ln in g["coordinates"]:
                out.append([[round(c[1], 5), round(c[0], 5)] for c in ln])
    return out


# ---------- 1. Área de estudio: HydroBASINS L12 que contienen los puntos, unidas ----------
# (los 117 puntos abarcan varias cuencas tributarias del Cauca: Amaime, Bolo, Guabas...)
hb = ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_12").filterBounds(pts)
nivel = "12"
n = hb.size().getInfo()
cuenca = hb.geometry().dissolve(maxError=50)
cuenca_gj = cuenca.getInfo()
area_km2 = cuenca.area(maxError=50).getInfo() / 1e6
b = cuenca.bounds().getInfo()["coordinates"][0]
lons = [c[0] for c in b]; lats = [c[1] for c in b]
print(f"Área de estudio: {n} sub-cuencas HydroBASINS L{nivel} unidas -> {area_km2:,.0f} km2")
print(f"  bbox lon [{min(lons):.4f}, {max(lons):.4f}]  lat [{min(lats):.4f}, {max(lats):.4f}]")

# ---------- 2. Rios (HydroSHEDS Free-Flowing Rivers) ----------
riv = ee.FeatureCollection("WWF/HydroSHEDS/v1/FreeFlowingRivers")
# red de la cuenca (recortada al polígono)
amaime = riv.filterBounds(cuenca).map(lambda f: f.intersection(cuenca, 30))
# Río Cauca: colector regional (descarga alta), en la franja oeste de la región
cauca = riv.filterBounds(region).filter(ee.Filter.gt("DIS_AV_CMS", 200))

print("tramos Amaime:", amaime.size().getInfo(), "| tramos Cauca:", cauca.size().getInfo())
amaime_lines = latlon_lines(amaime)
cauca_lines = latlon_lines(cauca)

out = {
    "cuenca": cuenca_gj,
    "cuenca_area_km2": round(area_km2),
    "amaime": amaime_lines,
    "cauca": cauca_lines,
}
(SP / "cuenca_amaime.json").write_text(json.dumps(out), encoding="utf-8")
kb = len((SP / "cuenca_amaime.json").read_text(encoding="utf-8")) / 1024
print(f"cuenca_amaime.json escrito ({kb:.0f} KB) | red cuenca {len(amaime_lines)} polilíneas, "
      f"Cauca {len(cauca_lines)} polilíneas")

# también como GeoPackage (EPSG:3115) para usarlo de máscara en el notebook
gpd.GeoDataFrame({"nombre": ["Area_estudio_HydroBASINS_L12"]},
                geometry=[sg.shape(cuenca_gj)], crs="EPSG:4326") \
    .to_crs("EPSG:3115").to_file(ENT / "Cuenca_estudio.gpkg", driver="GPKG")
print("Entrada/Cuenca_estudio.gpkg escrito (EPSG:3115)")
