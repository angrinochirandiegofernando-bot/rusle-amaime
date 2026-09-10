# Erodabilidad y pérdidas de suelo por erosión hídrica — Cuenca del río Amaime

Flujo de trabajo reproducible (Jupyter) para estimar la **erodabilidad de los
suelos** y las **pérdidas de suelo por erosión hídrica** en la cuenca del río
Amaime (Valle del Cauca, Colombia) con el modelo **USLE/RUSLE**:

```
A = R · K · LS · C · P
```

Los insumos raster (DEM, precipitación, cobertura) se **descargan automáticamente
desde la API de Google Earth Engine**; los resultados se calculan tanto en los
**117 puntos de muestreo** como en **rásteres continuos a 30 m**.

## Objetivos

**General.** Determinar la erodabilidad de los suelos de la cuenca como estrategia
para su conservación.

| # | Objetivo específico | Sección del notebook |
|---|---|---|
| I | Caracterizar las propiedades físicas y químicas de los suelos | 19 |
| II | Establecer la erodabilidad mediante el factor **K** y su relación con dichas propiedades | 20 |
| III | Evaluar el riesgo potencial de erosión hídrica mediante el índice **LS × R** | 24 |
| IV | Estimar las pérdidas de suelo y su distribución espacial | 25 |
| V | Modelar la variación temporal de las pérdidas 2010–2025 actualizando el factor **R** | 26 |

## Estructura

```
.
├── Script/RUSLE_Amaime_FACTOR_R_CORREGIDO_COLAB.ipynb   notebook principal (29 secciones)
├── scripts/
│   ├── analisis_mensual.py        precipitación y erosividad mes a mes (2010–2025)
│   └── mapa_deslizamientos.py     mapa HTML de susceptibilidad a movimientos en masa
├── docs/                          mapas interactivos (los sirve GitHub Pages)
│   ├── index.html
│   ├── mapa-deslizamientos.html
│   └── mapa-ls.html
├── Entrada/    (no versionada)    Cuenca amaime.xlsx · Cuenca Amaime Tesis Dayana.xlsx
├── Salida/     (no versionada)    todos los rásteres, tablas y mapas que genera el notebook
├── requirements.txt
└── .gitignore
```

`Entrada/` y `Salida/` **no se versionan** (ver `.gitignore`): `Salida/` supera el
límite de tamaño de GitHub y se regenera al ejecutar el notebook; los datos de
`Entrada/` incluyen la base de suelos de la tesis, propiedad de su autora.

## Requisitos

- Python 3.11 o superior — `pip install -r requirements.txt`
- Una cuenta habilitada en **Google Earth Engine** y un proyecto de Google Cloud.
  El notebook usa `EE_PROJECT = 'ee-pracagro2'`; cámbialo por el tuyo en la
  Sección 1.

## Cómo ejecutar

1. **Autenticar Earth Engine** (solo la primera vez en cada equipo):
   ```python
   import ee; ee.Authenticate()
   ```
2. **Colocar los insumos** en `Entrada/`:
   - `Cuenca amaime.xlsx` — 117 puntos de muestreo (coordenadas `LONG/LAT`, `COOR_X/COOR_Y`).
   - `Cuenca Amaime Tesis Dayana.xlsx` — hoja `Datos`, con textura, materia
     orgánica, estructura, permeabilidad y química por punto.
3. **Ejecutar el notebook** de principio a fin (`Script/RUSLE_Amaime_FACTOR_R_CORREGIDO_COLAB.ipynb`).
   La primera corrida descarga el DEM y CHIRPS y calcula la cadena hidrológica
   (varios minutos); las siguientes reutilizan lo que ya esté en `Salida/`.
   Para forzar la redescarga: `FORZAR_DESCARGA_EE = True`.

## Salidas (en `Salida/`)

- **Tabla integrada:** `Cuenca_amaime_completo.xlsx` / `.gpkg` (117 puntos × todos los factores y resultados).
- **Rásteres de factores:** `Factor_K.tif`, `Factor_C.tif`, `Factor_P.tif`, `Factor_R_climatologico.tif`, `Factor_R_promedio_2010_2025.tif`.
- **Pérdida de suelo:** `A_USLE_climatologico.tif`, `A_USLE_promedio.tif`, `A_USLE_anual_2010_2025.tif` (16 bandas), `Tendencia_A_2010_2025.tif`.
- **Riesgo y conservación:** `Riesgo_LSxR.tif`, `Areas_prioritarias_conservacion.tif`.
- **Susceptibilidad a deslizamientos:** `Susceptibilidad_MM_lluvia_media.tif`, `..._extrema.tif`, `Humedad_topografica_TWI.tif`.
- **Tablas resumen (CSV):** caracterización de suelos, correlación K–propiedades, resumen por clase de erosión, resumen de riesgo, serie temporal anual y mensual, síntesis por objetivo.
- **Mapas interactivos (HTML):** susceptibilidad a deslizamientos y factor LS.

## Metodología (resumen)

- **LS** — Mitasova & Mitas (2001), sobre acumulación de flujo D8 (WhiteboxTools); umbral de red de drenaje = 50 celdas.
- **R** — Índice de Fournier Modificado (MFI) → R (Renard & Freimund, 1994), a partir de CHIRPS diario.
- **K** — Wischmeier & Smith (1978) a partir de textura + materia orgánica + estructura + permeabilidad, en unidades SI.
- **C** — factor de cobertura por punto (estudio de uso del suelo) y por ráster (tabla sobre ESA WorldCover v200).
- **P** — factor de prácticas por punto; escenario base P = 1 para el ráster.
- **Clases de pérdida de suelo** — FAO‑PNUMA‑UNESCO (1980): ninguna/ligera <10, moderada 10–50, alta 50–200, muy alta >200 t·ha⁻¹·año⁻¹.

## Alcance y limitaciones

- El factor **R** usa la ecuación MFI→R de Renard & Freimund (1994), que en clima
  húmedo tropical tiende a valores altos; conviene leer las pérdidas en términos
  **relativos / de clases** y, de ser posible, validar R contra $EI_{30}$ de
  pluviógrafos locales.
- El **mapa de susceptibilidad a deslizamientos** (`scripts/mapa_deslizamientos.py`)
  es un índice heurístico de tamizaje (pendiente + humedad topográfica TWI +
  lluvia). **No** modela movimientos en masa con base geotécnica: no incluye
  geología, espesor de suelo ni sismicidad, y no está calibrado con un inventario
  de deslizamientos. RUSLE modela erosión hídrica **laminar y en surcos**, que es
  un proceso distinto.
- El límite de análisis es la **zona de influencia** (envolvente de los 117 puntos
  + buffer de 5 km), no el parteaguas hidrográfico oficial.

## Referencias

Wischmeier & Smith (1978, USDA AH‑537) · Renard et al. (1997, USDA AH‑703) ·
Renard & Freimund (1994, *J. Hydrol.* 157) · Mitasova et al. (1996, *Int. J. GIS*
10) · Arnoldus (1980) · FAO‑PNUMA‑UNESCO (1980) · Funk et al. (2015, CHIRPS,
*Sci. Data* 2) · ESA WorldCover (2021) · Lindsay (2016, WhiteboxTools).
