# Directiva de Proyecto: Analizador de Gastos de Uber/Didi

## Estado del Proyecto: v2.0 - AUTOMATIZADO CON WEB UI

Este proyecto analiza recibos de Uber/Didi desde archivos .eml para separar gastos personales de laborales y generar reportes para reintegros. Version 2.0 agrega: SQLite database, interfaz web Flask, Gmail API, y pipeline automatizado.

---

## Objetivos Logrados

1. Parser robusto que extrae datos de recibos de **Uber** y **Didi**
2. Sistema de deduplicacion automatica (DB UNIQUE constraint)
3. Auto-categorizacion basada en direcciones conocidas (configurables)
4. Generacion de CSV con datos para reintegros
5. **Conversion automatica HTML -> PDF usando Playwright** (batch optimizado)
6. Reportes mensuales con totales
7. **Base de datos SQLite** como fuente de verdad
8. **Interfaz web Flask** con Bootstrap + htmx (edicion inline de categorias)
9. **Gmail API** para descarga automatica de recibos
10. **Pipeline unificado** (un comando para todo el flujo)

---

## Estructura del Proyecto

```
Analisis_Uber/
├── config/                          # Configuracion
│   ├── credentials.json             # Gmail API (usuario provee)
│   ├── token.json                   # Auto-generado por OAuth
│   └── settings.json                # Direcciones de trabajo editables
│
├── data/                            # Base de datos
│   └── expense_tracker.db           # SQLite
│
├── services/                        # Logica de negocio
│   ├── __init__.py
│   ├── database.py                  # Schema SQLite + queries
│   ├── gmail_service.py             # Gmail API download
│   ├── categorizer.py               # Auto-categorizacion (refactored)
│   ├── pipeline.py                  # Orquestador unificado
│   └── task_runner.py               # Executor de tareas background
│
├── web/                             # Interfaz web Flask
│   ├── __init__.py                  # App factory
│   ├── routes/
│   │   ├── dashboard.py             # Pagina principal con stats
│   │   ├── trips.py                 # Lista + editor de categorias (htmx)
│   │   ├── gmail.py                 # Descarga de Gmail
│   │   ├── reports.py               # Summary + generacion PDFs
│   │   └── settings.py              # Direcciones configurables
│   └── templates/                   # Jinja2 con Bootstrap + htmx
│
├── receipts/                        # Archivos .eml descargados
├── output/                          # Reportes generados
├── reintegros/                      # PDFs listos para reintegro
│
├── parser.py                        # Logica de parsing Uber/Didi
├── main.py                          # Script principal (CLI con flags)
├── generar_reintegros.py            # Genera PDFs y CSV de reintegro
├── auto_categorize.py               # Wrapper de services/categorizer
├── migrate_csv.py                   # Migracion unica CSV -> SQLite
├── run_web.py                       # Entry point web
├── requirements.txt                 # Dependencias
├── README.md                        # Documentacion para usuarios
├── EJEMPLO_CATEGORIZACION.md        # Reglas de categorizacion VALIDADAS
└── CLAUDE.md                        # Este archivo (directivas tecnicas)
```

---

## Scripts Disponibles

### 1. `python main.py` (Original - sin cambios)
Parsear recibos y generar CSV. Igual que antes.

### 2. `python main.py --summary` (Original - sin cambios)
Generar reporte de totales desde CSV.

### 3. `python main.py --db`
Parsear recibos y guardar en base de datos SQLite.

### 4. `python main.py --summary --db`
Generar reporte desde base de datos.

### 5. `python main.py --download`
Descargar nuevos recibos desde Gmail (requiere credentials.json en config/).

### 6. `python main.py --pipeline`
Pipeline completo automatizado: Parse -> Dedup -> Categorize -> Summary -> PDFs

### 7. `python main.py --web`
Lanzar interfaz web en localhost:5000

### 8. `python run_web.py`
Alternativa directa para lanzar la web (abre browser automaticamente).

### 9. `python migrate_csv.py`
Migracion unica del CSV existente a SQLite.

### 10. `python generar_reintegros.py`
Generar PDFs (modo CSV). Con --db internamente desde la web.

---

## Base de Datos SQLite

**Archivo:** `data/expense_tracker.db`

**Tablas:**
- `trips` - Viajes con deduplicacion UNIQUE(date, service, amount, origin, destination)
- `downloaded_emails` - Tracking de emails descargados (evita re-descargas)
- `pipeline_runs` - Historial de ejecuciones del pipeline

**Ventajas sobre CSV:**
- Deduplicacion automatica via UNIQUE constraint
- Queries eficientes para filtros y estadisticas
- Concurrencia segura (WAL mode)
- No hay problemas de separadores (`;` vs `,`)

---

## Interfaz Web

**URL:** http://localhost:5000

**Paginas:**
- **Dashboard (/):** Stats generales, breakdown Laburo/Personal, acciones rapidas
- **Viajes (/trips):** Tabla con dropdown de categoria por fila (htmx inline edit), filtros por mes/categoria
- **Gmail (/gmail):** Estado de conexion, descarga de recibos, historial
- **Reportes (/reports):** Generar summary, PDFs (con progress), pipeline completo
- **Config (/settings):** Editar direcciones de trabajo/casa, ver estado del sistema

**Stack:** Flask + Bootstrap 5 CDN + htmx CDN (sin Node.js)

---

## Reglas de Categorizacion

### REGLA DE ORO

**Un viaje es LABURO si involucra CUALQUIERA de estas direcciones:**

1. **Oficina Principal:** `Leandro N. Alem 815`
2. **Oficina/Cliente Puerto Madero:** `Juana Manso` (cualquier numero)
3. **Cliente Munro:** `Alferez Hipolito Bouchard` o `Alferez Hipolito Bouchard`
4. **Otros Clientes:** `Dorrego 2520`, `Cordoba 111`, `Torre BBVA`

**Si hay una direccion de trabajo involucrada, ES LABURO, sin importar que el otro extremo sea tu casa.**

### Direcciones configurables

Las direcciones se configuran en `config/settings.json` o desde la web UI en /settings.

---

## Flujo de Trabajo Completo

### Opcion A: Web UI (Recomendada)
```bash
python main.py --web          # Abre http://localhost:5000
# 1. Dashboard -> Pipeline completo (o pasos individuales)
# 2. Viajes -> Revisar/editar categorias con dropdown
# 3. Reportes -> Generar PDFs
```

### Opcion B: CLI Automatizado
```bash
python main.py --pipeline     # Todo automatico
# Revisa output/summary.md y reintegros/
```

### Opcion C: CLI Manual (Original)
```bash
python main.py                # Parsear a CSV
# Editar CSV en Excel
python main.py --summary      # Generar reporte
python generar_reintegros.py  # Generar PDFs
```

---

## Tecnologias y Dependencias

```
beautifulsoup4>=4.12.0    # Parsing HTML
lxml>=4.9.0               # Parser backend
pandas>=2.1.0             # CSV y analisis
playwright>=1.40.0        # Conversion HTML->PDF
flask>=3.0.0              # Interfaz web

# Opcionales (Gmail API):
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.1
google-auth-oauthlib>=1.1.0
```

**Instalacion:**
```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

---

## Datos de la Ultima Ejecucion

**Recibos procesados:** 21 archivos .eml
**Duplicados eliminados:** 3
**Viajes unicos:** 18

**Categorizacion:**
- **Laburo:** 10 viajes -> ARS 179,859.34 (para reintegro)
- **Personal:** 8 viajes -> ARS 86,585.00

**Periodo:** Diciembre 2025 - Febrero 2026

---

## Problemas Conocidos y Soluciones

### 1. CSV cambia separador de `,` a `;`
**Solucion:** Auto-deteccion de separador en todos los scripts.

### 2. Errores de encoding en Windows
**Solucion:** Solo ASCII en prints, utf-8-sig para archivos.

### 3. WeasyPrint no funciona en Windows
**Solucion:** Playwright con navegador headless.

### 4. Playwright lento con muchos PDFs
**Solucion:** Batch mode - un solo browser instance para todos los PDFs.

---

## Notas para Claude (IA)

### Al retomar este proyecto:

1. **SIEMPRE lee primero:**
   - `EJEMPLO_CATEGORIZACION.md` (reglas validadas)
   - Este archivo (CLAUDE.md)

2. **NO asumas** que Casa -> Trabajo = Personal
   - Cualquier viaje con direccion de trabajo = LABURO

3. **Arquitectura:**
   - `services/` contiene toda la logica de negocio
   - `web/` contiene Flask routes y templates
   - `config/settings.json` tiene direcciones configurables
   - `data/expense_tracker.db` es la fuente de verdad

4. **CLI es backward compatible:**
   - `python main.py` y `python main.py --summary` funcionan identico al original
   - Nuevas flags: `--db`, `--pipeline`, `--web`, `--download`

5. **Para Gmail API:**
   - El usuario debe proveer `config/credentials.json`
   - Token se genera automaticamente en `config/token.json`

6. **Web UI:**
   - htmx maneja edicion inline de categorias sin JavaScript custom
   - Task runner ejecuta PDFs y Gmail en background
   - Templates usan Bootstrap 5 + htmx via CDN

---

**Ultima actualizacion:** 2026-02-07
**Status:** Produccion - v2.0 con Web UI
**Monto procesado:** ARS 266,444.34
**Monto para reintegro:** ARS 179,859.34
