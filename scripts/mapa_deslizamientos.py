# -*- coding: utf-8 -*-
"""Mapa HTML interactivo de susceptibilidad a movimientos en masa (deslizamientos)
para la cuenca del Amaime, combinando factores topográficos (pendiente + humedad
topográfica TWI) y precipitación (CHIRPS), en dos escenarios de lluvia.

NOTA: índice heurístico topográfico-hidrológico de tamizaje (estilo Mora-Vahrson,
sin término sísmico ni inventario de deslizamientos). No sustituye un estudio
geotécnico. RUSLE (erosión laminar) es un proceso distinto.
"""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import Normalize, ListedColormap
import branca.colormap as bcm
import folium
from folium.plugins import MeasureControl, Fullscreen

import os
# raíz del proyecto: variable de entorno RUSLE_BASE, o la carpeta que contiene /scripts
DIR_BASE = Path(os.environ.get("RUSLE_BASE", Path(__file__).resolve().parents[1]))
SAL = DIR_BASE / "Salida"
RAST = SAL / "rasters"; TAB = SAL / "tablas"; MAP = SAL / "mapas"; FIG = SAL / "figuras"
for _d in (RAST, TAB, MAP, FIG): _d.mkdir(parents=True, exist_ok=True)
DEM_F = RAST / "DEM_Amaime_Copernicus30m.tif"
SLOPE_F = RAST / "Pendiente_grados.tif"
FACC_F = RAST / "Flow_Accumulation.tif"
STREAMS_F = RAST / "Streams.tif"
CHIRPS_F = RAST / "CHIRPS_Mensual_Climatologia_Amaime_2020_2025.tif"
ZONA_F = TAB / "Zona_Influencia.gpkg"
PUNTOS_F = TAB / "Cuenca_amaime_completo.gpkg"
CELL = 30.0
OUT_HTML = MAP / "Mapa_Susceptibilidad_Deslizamientos_Amaime.html"
ASSETS = SAL / "_assets_mapa_deslizamientos"
ASSETS.mkdir(exist_ok=True)


def leer(f, banda=1):
    with rasterio.open(f) as s:
        a = s.read(banda).astype("float32")
        a = np.where(a == s.nodata, np.nan, a)
        return a, s.profile.copy()


# ---------- 1. factores topográficos ----------
slope, perf = leer(SLOPE_F)
facc, _ = leer(FACC_F)
streams, _ = leer(STREAMS_F)

slope_rad = np.radians(np.clip(slope, 0.1, 89))
As = np.clip(facc, 1, None) * CELL                       # área de captación específica
TWI = np.log(As / np.tan(slope_rad))                     # humedad topográfica
TWI = np.clip(TWI, np.nanpercentile(TWI, 1), np.nanpercentile(TWI, 99))

# ---------- 2. precipitación (CHIRPS anual, remuestreada a la malla) ----------
with rasterio.open(CHIRPS_F) as s:
    p12 = s.read().astype("float64")
    pprof = s.profile.copy()
p_anual_native = np.nansum(p12, axis=0).astype("float32")
p_anual = np.full((perf["height"], perf["width"]), np.nan, "float32")
reproject(p_anual_native, p_anual,
          src_transform=pprof["transform"], src_crs=pprof["crs"],
          dst_transform=perf["transform"], dst_crs=perf["crs"],
          resampling=Resampling.bilinear)


def norm01(x):
    lo, hi = np.nanpercentile(x, 2), np.nanpercentile(x, 98)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


pend_n = norm01(slope)
twi_n = norm01(TWI)
lluvia_media_n = norm01(p_anual)
lluvia_extrema_n = np.clip(lluvia_media_n * 1.35 + 0.15, 0, 1)     # escenario húmedo

# ---------- 3. índice de susceptibilidad (dos escenarios) ----------
mascara = np.isfinite(slope)
zona = gpd.read_file(ZONA_F).to_crs(perf["crs"])
from rasterio.features import geometry_mask
dentro = ~geometry_mask(list(zona.geometry), (perf["height"], perf["width"]),
                        perf["transform"], invert=False)
mascara &= dentro


def indice(lluvia_n):
    idx = 0.45 * pend_n + 0.25 * twi_n + 0.30 * lluvia_n
    idx = np.where(mascara, idx, np.nan)
    return idx


idx_media = indice(lluvia_media_n)
idx_extrema = indice(lluvia_extrema_n)

# clases por quintiles del escenario medio (mismos cortes para ambos)
q = np.nanpercentile(idx_media[np.isfinite(idx_media)], [20, 40, 60, 80])
NIVELES = ["Muy baja", "Baja", "Moderada", "Alta", "Muy alta"]
COLORES = ["#1a9850", "#a6d96a", "#fee08b", "#fdae61", "#d73027"]


def clasificar(idx):
    c = np.full(idx.shape, np.nan, "float32")
    b = [-np.inf, *q, np.inf]
    for i in range(5):
        c = np.where((idx > b[i]) & (idx <= b[i + 1]), i + 1, c)
    return np.where(np.isfinite(idx), c, np.nan)


cls_media = clasificar(idx_media)
cls_extrema = clasificar(idx_extrema)

# guardar rásteres
for arr, name in [(idx_media, "Susceptibilidad_MM_lluvia_media.tif"),
                  (idx_extrema, "Susceptibilidad_MM_lluvia_extrema.tif"),
                  (TWI, "Humedad_topografica_TWI.tif")]:
    pp = perf.copy(); pp.update(dtype="float32", count=1, nodata=np.nan)
    with rasterio.open(SAL / name, "w", **pp) as d:
        d.write(np.where(mascara, arr, np.nan).astype("float32"), 1)

# ---------- 4. reproyectar a 4326 y exportar PNG para folium ----------
def a_4326_png(arr, cmap, vmin, vmax, fname, discrete=False):
    dst_crs = "EPSG:4326"
    t, w, h = calculate_default_transform(perf["crs"], dst_crs, perf["width"],
                                          perf["height"], *rasterio.transform.array_bounds(
                                              perf["height"], perf["width"], perf["transform"]))
    out = np.full((h, w), np.nan, "float32")
    reproject(arr.astype("float32"), out, src_transform=perf["transform"], src_crs=perf["crs"],
              dst_transform=t, dst_crs=dst_crs,
              resampling=Resampling.nearest if discrete else Resampling.bilinear)
    b = rasterio.transform.array_bounds(h, w, t)          # (left, bottom, right, top)
    bounds = [[b[1], b[0]], [b[3], b[2]]]
    if discrete:
        rgba = ListedColormap(cmap)((np.clip(out, 1, 5) - 1) / 4)
    else:
        rgba = cm.get_cmap(cmap)(Normalize(vmin, vmax)(out))
    rgba[..., 3] = np.where(np.isfinite(out), 0.75, 0)
    plt.imsave(ASSETS / fname, rgba)
    return str((ASSETS / fname).as_posix()), bounds


png_media, bnd = a_4326_png(cls_media, COLORES, 1, 5, "susc_media.png", discrete=True)
png_extr, _ = a_4326_png(cls_extrema, COLORES, 1, 5, "susc_extrema.png", discrete=True)
png_slope, _ = a_4326_png(slope, "YlOrRd", 0, np.nanpercentile(slope, 98), "slope.png")
png_twi, _ = a_4326_png(TWI, "Blues", np.nanmin(TWI), np.nanmax(TWI), "twi.png")

# streams a 4326 (solo píxeles de cauce) como PNG azul
strm = np.where(streams == 1, 1.0, np.nan)
png_str, _ = a_4326_png(strm, "cool", 0, 1, "streams.png")

# ---------- 5. puntos: muestrear el índice y su clase ----------
pts = gpd.read_file(PUNTOS_F).to_crs("EPSG:4326")
pts_m = gpd.read_file(PUNTOS_F).to_crs(perf["crs"])
with rasterio.open(RAST / "Susceptibilidad_MM_lluvia_media.tif") as s:
    coords = [(g.x, g.y) for g in pts_m.geometry]
    vals = [v[0] for v in s.sample(coords)]
pts["susc_idx"] = vals
b = [-np.inf, *q, np.inf]
pts["susc_nivel"] = np.select([(pts.susc_idx > b[i]) & (pts.susc_idx <= b[i + 1]) for i in range(5)],
                              [1, 2, 3, 4, 5], default=np.nan)

# ---------- 6. mapa folium ----------
cen = [pts.geometry.y.mean(), pts.geometry.x.mean()]
m = folium.Map(location=cen, zoom_start=12, control_scale=True, tiles=None)
folium.TileLayer("OpenStreetMap", name="Calles").add_to(m)
folium.TileLayer("Esri.WorldImagery", name="Satélite", attr="Esri").add_to(m)

folium.raster_layers.ImageOverlay(png_media, bnd, opacity=0.75,
                                  name="Susceptibilidad — lluvia MEDIA").add_to(m)
folium.raster_layers.ImageOverlay(png_extr, bnd, opacity=0.75, show=False,
                                  name="Susceptibilidad — lluvia EXTREMA").add_to(m)
folium.raster_layers.ImageOverlay(png_slope, bnd, opacity=0.6, show=False,
                                  name="Pendiente (°)").add_to(m)
folium.raster_layers.ImageOverlay(png_twi, bnd, opacity=0.6, show=False,
                                  name="Humedad topográfica (TWI)").add_to(m)
folium.raster_layers.ImageOverlay(png_str, bnd, opacity=0.9, show=False,
                                  name="Red de drenaje").add_to(m)

fg = folium.FeatureGroup(name="Puntos de muestreo (117)")
for _, r in pts.iterrows():
    niv = int(r.susc_nivel) if np.isfinite(r.susc_nivel) else 0
    col = COLORES[niv - 1] if niv else "#888"
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x], radius=4 + (niv or 0),
        color="black", weight=.6, fill=True, fill_color=col, fill_opacity=.9,
        tooltip=f"{r.get('ID_UNAL', '')} · susceptibilidad {NIVELES[niv-1] if niv else 'ND'}",
        popup=folium.Popup(
            f"<b>{r.get('ID_UNAL','')}</b><br>Nivel: {NIVELES[niv-1] if niv else 'ND'}<br>"
            f"Índice: {r.susc_idx:.2f}<br>Pendiente: {r.get('Pendiente_pct', float('nan')):.1f}%<br>"
            f"LS: {r.get('LS_Mitasova', float('nan')):.1f}", max_width=260),
    ).add_to(fg)
fg.add_to(m)

leg = bcm.StepColormap(COLORES, vmin=0, vmax=5, index=[0, 1, 2, 3, 4, 5],
                       caption="Susceptibilidad a movimientos en masa (índice topográfico-hidrológico)")
m.add_child(leg)
folium.LayerControl(collapsed=False).add_to(m)
m.add_child(MeasureControl()); m.add_child(Fullscreen())

titulo = ('<div style="position:fixed;top:8px;left:50px;z-index:9999;background:white;'
          'padding:6px 12px;border:1px solid #999;border-radius:4px;font:13px Arial">'
          '<b>Cuenca del río Amaime — Susceptibilidad a deslizamientos</b><br>'
          '<span style="font-size:11px">Índice heurístico: 0,45·pendiente + 0,25·humedad topográfica + 0,30·lluvia. '
          'Escenarios de lluvia media/extrema conmutables. Tamizaje, no sustituye estudio geotécnico.</span></div>')
m.get_root().html.add_child(folium.Element(titulo))
m.save(str(OUT_HTML))

# resumen ha por nivel (para el texto, no como tabla en el mapa)
apx = (CELL ** 2) / 1e4
print("HTML:", OUT_HTML)
for esc, cl in [("lluvia media", cls_media), ("lluvia extrema", cls_extrema)]:
    tot = np.isfinite(cl).sum()
    print(f"\n{esc}:")
    for i, n in enumerate(NIVELES, 1):
        k = int((cl == i).sum())
        print(f"  {n:10s}: {k*apx:8,.0f} ha  ({100*k/tot:5.1f}%)")
