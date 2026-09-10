# -*- coding: utf-8 -*-
"""Análisis mensual de precipitación y erosividad (2010-2025) para la cuenca del Amaime.
Genera PNGs en Salida/ mostrando cómo la erosividad (y por tanto la pérdida de suelo)
se distribuye mes a mes con la precipitación CHIRPS."""
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import ee

import os
# raíz del proyecto: variable de entorno RUSLE_BASE, o la carpeta que contiene /scripts
DIR_BASE = Path(os.environ.get("RUSLE_BASE", Path(__file__).resolve().parents[1]))
DIR_SAL = DIR_BASE / "Salida"
Y0, Y1 = 2010, 2025
MESES_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

ee.Initialize(project="ee-pracagro2")
print("EE OK")

# --- Región = Zona de Influencia ---
zona = gpd.read_file(DIR_SAL / "Zona_Influencia.gpkg").to_crs(4326)
region = ee.Geometry(zona.geometry.iloc[0].__geo_interface__)

# --- Precipitación mensual media de la cuenca, 2010-2025 (CHIRPS diario -> suma mensual) ---
chirps = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
          .filterDate(f"{Y0}-01-01", f"{Y1 + 1}-01-01")
          .filterBounds(region).select("precipitation"))

pares = []
for y in range(Y0, Y1 + 1):
    for m in range(1, 13):
        pares.append((y, m))

def suma_mes(par):
    y, m = ee.Number(ee.List(par).get(0)), ee.Number(ee.List(par).get(1))
    img = (chirps.filter(ee.Filter.calendarRange(y, y, "year"))
           .filter(ee.Filter.calendarRange(m, m, "month")).sum())
    val = img.reduceRegion(ee.Reducer.mean(), region, 5566, maxPixels=1e9).get("precipitation")
    return ee.Feature(None, {"anio": y, "mes": m, "P_mm": val})

fc = ee.FeatureCollection(ee.List(pares).map(suma_mes))
rows = fc.getInfo()["features"]
df = pd.DataFrame([r["properties"] for r in rows]).sort_values(["anio", "mes"]).reset_index(drop=True)
df["P_mm"] = pd.to_numeric(df["P_mm"], errors="coerce")
df["fecha"] = pd.to_datetime(dict(year=df.anio, month=df.mes, day=15))
print("meses obtenidos:", len(df), "| P_mm rango:", round(df.P_mm.min(), 1), "-", round(df.P_mm.max(), 1))

# --- Erosividad: MFI y R anuales (fórmula establecida) + reparto mensual ---
def factor_r(mfi):
    return np.where(mfi < 55, 0.7397 * mfi ** 1.847, 95.77 - 6.081 * mfi + 0.4770 * mfi ** 2)

ann = df.groupby("anio").agg(P_anual=("P_mm", "sum"), sumP2=("P_mm", lambda s: (s ** 2).sum())).reset_index()
ann["MFI"] = ann.sumP2 / ann.P_anual
ann["R"] = factor_r(ann.MFI.values)
df = df.merge(ann[["anio", "P_anual", "sumP2", "MFI", "R"]], on="anio")
# aporte de cada mes al MFI y al R (pesos = P_mes^2)
df["aporte_MFI"] = df.P_mm ** 2 / df.P_anual
df["R_mes"] = df.R * (df.P_mm ** 2 / df.sumP2)     # sum_mes(R_mes) = R_anual

df.to_csv(DIR_SAL / "Serie_mensual_P_erosividad_2010_2025.csv", index=False)

# climatología mensual (media 2010-2025)
clim = df.groupby("mes").agg(P_mm=("P_mm", "mean"), P_sd=("P_mm", "std"),
                             R_mes=("R_mes", "mean"), aporte_MFI=("aporte_MFI", "mean")).reset_index()

# =====================================================================
# FIG A — Climatología mensual: precipitación vs erosividad
# =====================================================================
fig, ax1 = plt.subplots(figsize=(11, 5.5))
ax1.bar(clim.mes, clim.P_mm, yerr=clim.P_sd, capsize=3, color="#4575b4", alpha=.8,
        label="Precipitación media")
ax1.set_xticks(range(1, 13)); ax1.set_xticklabels(MESES_ES)
ax1.set_ylabel("Precipitación media mensual (mm)", color="#4575b4")
ax1.tick_params(axis="y", labelcolors="#4575b4") if False else ax1.tick_params(axis="y", colors="#4575b4")
ax2 = ax1.twinx()
ax2.plot(clim.mes, clim.R_mes, "o-", color="#d73027", lw=2.2, label="Erosividad media (aporte mensual a R)")
ax2.set_ylabel("Erosividad mensual  —  aporte a R  (MJ·mm·ha⁻¹·h⁻¹)", color="#d73027")
ax2.tick_params(axis="y", colors="#d73027")
ax1.set_title("Cuenca del río Amaime — Climatología mensual 2010–2025\n"
              "La erosividad se concentra en los meses lluviosos (relación cuadrática con la lluvia)",
              fontweight="bold")
ax1.grid(axis="y", alpha=.25)
fig.tight_layout()
fig.savefig(DIR_SAL / "Erosividad_mensual_climatologia.png", dpi=150)
plt.close(fig)

# =====================================================================
# FIG B — Serie mensual completa 2010-2025 (2 paneles)
# =====================================================================
fig, axes = plt.subplots(2, 1, figsize=(14, 7.5), sharex=True)
axes[0].fill_between(df.fecha, df.P_mm, color="#4575b4", alpha=.35)
axes[0].plot(df.fecha, df.P_mm, color="#2c5aa0", lw=1)
axes[0].set_ylabel("Precipitación\nmensual (mm)")
axes[0].set_title("Cuenca del río Amaime — Serie mensual 2010–2025 (CHIRPS, media de cuenca)",
                  fontweight="bold")
axes[1].fill_between(df.fecha, df.R_mes, color="#d73027", alpha=.35)
axes[1].plot(df.fecha, df.R_mes, color="#a01e1e", lw=1)
axes[1].set_ylabel("Erosividad mensual\n(aporte a R)")
axes[1].set_xlabel("Año")
axes[1].xaxis.set_major_locator(mdates.YearLocator())
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
for ax in axes:
    ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(DIR_SAL / "Erosividad_mensual_serie_2010_2025.png", dpi=150)
plt.close(fig)

# =====================================================================
# FIG C — Relación precipitación mensual  ->  erosividad mensual
# =====================================================================
fig, ax = plt.subplots(figsize=(8.5, 6))
sc = ax.scatter(df.P_mm, df.R_mes, c=df.mes, cmap="twilight", s=32, edgecolor="0.3", lw=.3)
xx = np.linspace(0, df.P_mm.max(), 100)
# ajuste cuadrático simple para ilustrar la forma
cf = np.polyfit(df.P_mm, df.R_mes, 2)
ax.plot(xx, np.polyval(cf, xx), "k--", lw=1.5, label="ajuste cuadrático")
_r_pm = np.corrcoef(df.P_mm, df.R_mes)[0, 1]
_r_pm2 = np.corrcoef(df.P_mm ** 2, df.R_mes)[0, 1]
ax.set_xlabel("Precipitación mensual (mm)")
ax.set_ylabel("Erosividad mensual (aporte a R)")
ax.set_title("Cuenca del río Amaime — La erosividad crece con el cuadrado de la lluvia mensual\n"
             f"192 meses, 2010–2025   ·   r(P, erosiv.) = {_r_pm:.2f}   ·   r(P², erosiv.) = {_r_pm2:.2f}",
             fontweight="bold")
cb = fig.colorbar(sc, ax=ax, ticks=range(1, 13)); cb.ax.set_yticklabels(MESES_ES); cb.set_label("Mes")
ax.legend(); ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(DIR_SAL / "Erosividad_vs_precipitacion_mensual.png", dpi=150)
plt.close(fig)

# =====================================================================
# FIG D — Anual: precipitación total vs Factor R (16 años) — enlace con Obj. V
#         Panel 1: series normalizadas (se mueven juntas).  Panel 2: dispersión con r.
# =====================================================================
r_pr = np.corrcoef(ann.P_anual, ann.R)[0, 1]
fig, ax = plt.subplots(1, 2, figsize=(14, 5))

ax[0].plot(ann.anio, ann.P_anual / ann.P_anual.mean(), "o-", color="#4575b4", lw=2,
           label="Precipitación anual (÷ media)")
ax[0].plot(ann.anio, ann.R / ann.R.mean(), "s-", color="#d73027", lw=2,
           label="Factor R anual (÷ media)")
ax[0].axhline(1, color="0.6", lw=.8)
ax[0].set_title("Series normalizadas: la erosividad sigue a la lluvia,\n"
                "pero con oscilaciones más amplias (dependencia cuadrática)", fontweight="bold")
ax[0].set_xticks(ann.anio); ax[0].set_xticklabels(ann.anio, rotation=45)
ax[0].set_ylabel("valor / media del periodo"); ax[0].legend(); ax[0].grid(alpha=.25)

ax[1].scatter(ann.P_anual, ann.R, s=45, color="#7b3294", zorder=3)
for _, row in ann.iterrows():
    ax[1].annotate(int(row.anio), (row.P_anual, row.R), fontsize=7, xytext=(3, 3),
                   textcoords="offset points")
_xx = np.linspace(ann.P_anual.min(), ann.P_anual.max(), 100)
_cf = np.polyfit(ann.P_anual, ann.R, 2)
ax[1].plot(_xx, np.polyval(_cf, _xx), "k--", lw=1.4)
ax[1].set_xlabel("Precipitación anual (mm)"); ax[1].set_ylabel("Factor R anual")
ax[1].set_title(f"Precipitación anual  vs  Factor R\nr = {r_pr:.2f}   (n = 16 años)", fontweight="bold")
ax[1].grid(alpha=.25)

fig.suptitle("Cuenca del río Amaime — Relación lluvia ↔ erosividad, 2010–2025 (Obj. V)",
             fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(DIR_SAL / "Precipitacion_vs_R_anual_2010_2025.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\ncorr(P_anual, R) anual = {r_pr:.3f}")

print("\nPNGs generados en Salida/:")
for p in ["Erosividad_mensual_climatologia.png", "Erosividad_mensual_serie_2010_2025.png",
          "Erosividad_vs_precipitacion_mensual.png", "Precipitacion_vs_R_anual_2010_2025.png"]:
    print("  ", p, "OK" if (DIR_SAL / p).exists() else "FALTA")
print("\nClimatología mensual:")
print(clim.round(1).to_string(index=False))
