# -*- coding: utf-8 -*-
"""Inyecta la hoja 'Precipitacion_mensual' (precipitación media mensual CHIRPS
2020–2025 por punto de muestreo + MFI + Factor R) dentro de
'Cuenca Amaime Tesis Dayana.xlsx'.

Uso: cerrar el Excel y ejecutar
    python scripts/agregar_hoja_precipitacion.py
Requiere haber corrido antes el notebook (genera Salida/Precipitacion_mensual_por_punto.csv).
"""
import os
from pathlib import Path
import pandas as pd

DIR_BASE = Path(os.environ.get("RUSLE_BASE", Path(__file__).resolve().parents[1]))
CSV = DIR_BASE / "Salida" / "tablas" / "Precipitacion_mensual_por_punto.csv"
XLSX = DIR_BASE / "Entrada" / "Cuenca Amaime Tesis Dayana.xlsx"
HOJA = "Precipitacion_mensual"

if not CSV.exists():
    raise SystemExit(f"No existe {CSV}. Corre primero el notebook.")
if not XLSX.exists():
    raise SystemExit(f"No existe {XLSX}.")

df = pd.read_csv(CSV)
print(f"Hoja a insertar: {df.shape[0]} filas x {df.shape[1]} columnas")
print("Columnas:", list(df.columns))

try:
    with pd.ExcelWriter(XLSX, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
        df.to_excel(xw, sheet_name=HOJA, index=False)
except PermissionError:
    raise SystemExit(f"'{XLSX.name}' está abierto en Excel. Ciérralo y vuelve a ejecutar.")

print(f"OK: hoja '{HOJA}' añadida/actualizada en {XLSX.name}")
