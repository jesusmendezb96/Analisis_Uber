# Directiva Tecnica: Analizador de Gastos Uber/Didi

> Documento interno para desarrollo con Claude Code. Contiene arquitectura, decisiones tecnicas, logica de negocio y guia de mantenimiento.

**Version:** 2.2
**Ultima actualizacion:** 2026-03-02
**Status:** Produccion

---

## 1. Arquitectura General

### 1.1 Resumen

El sistema procesa recibos de viajes Uber/Didi para separar gastos laborales de personales y generar archivos de reintegro corporativo. Opera en tres modos: CLI legacy (CSV), CLI automatizado (SQLite), e interfaz web (Flask).

### 1.2 Diagrama de Flujo de Datos

```
Gmail (emails .eml)
    |
    v
[gmail_service.py] -- OAuth2 --> Gmail API (readonly)
    |                             Filtro: subject:"Tu viaje" from:noreply@uber.com OR from:didi@...
    |                             Filtro anti-promo: excluye "cuesta menos", "OFF", "descuento"
    v
receipts/*.eml (archivos raw)
    |
    v
[parser.py] -- BeautifulSoup4 --> Extrae: fecha, origen, destino, monto, moneda, servicio
    |                              Uber: data-testid attrs + address-point-desc class
    |                              Didi: text parsing con regex (fechas en espanol, montos con $)
    |                              FECHA: parsedate_to_datetime() -> convertir a AR (UTC-3) antes de extraer
    v
[database.py] -- SQLite WAL --> data/expense_tracker.db
    |                            UNIQUE(date, service, amount, origin, destination) = deduplicacion
    |                            parse_all_receipts() skipea filenames ya en la tabla trips
    v
[categorizer.py] -- config/settings.json --> Laburo / Personal / needs_review
    |                                         Regla: work_address en origin OR destination = Laburo
    |                                         Categorias manuales (auto_categorized=0) NO se sobreescriben
    v
[main.py --summary] --> output/summary.md (Markdown con totales por categoria/mes/servicio)
    |
    v
[generar_reintegros.py] -- Playwright (Chromium headless) --> reintegros/*.pdf
                            Batch mode: 1 browser instance para N PDFs
                            Naming: {counter:02d}_{YYYYMMDD}_{service}_{currency}_{amount}.pdf
```

### 1.3 Stack Tecnologico

| Componente | Tecnologia | Justificacion |
|------------|-----------|---------------|
| Parsing HTML | BeautifulSoup4 + lxml | Robusto con HTML malformado de emails |
| Base de datos | SQLite (WAL mode) | Zero-install, UNIQUE constraints, concurrencia |
| Web framework | Flask + Jinja2 | Ligero, sin Node.js, templates server-side |
| Frontend interactivo | htmx 1.9 | Inline editing sin JavaScript custom |
| UI | Bootstrap 5 CDN | Responsive, sin build step |
| PDF generation | Playwright (Chromium) | Renderizado identico a browser real |
| Gmail | google-api-python-client | OAuth2 con auto-refresh de tokens |
| Background tasks | ThreadPoolExecutor | Sin dependencias externas (no Celery/Redis) |

### 1.4 Estructura del Proyecto

```
Analisis_Uber/
├── config/                          # Configuracion (excluido de git excepto settings.json)
│   ├── credentials.json             # Gmail OAuth client secret (usuario provee, NO en git)
│   ├── token.json                   # Auto-generado por OAuth flow (NO en git)
│   └── settings.json                # Direcciones de trabajo/casa (NO en git, local)
│
├── data/                            # Base de datos (NO en git)
│   └── expense_tracker.db           # SQLite - fuente de verdad en modo v2
│
├── services/                        # Capa de logica de negocio
│   ├── __init__.py
│   ├── database.py                  # Schema, queries, migraciones
│   ├── gmail_service.py             # OAuth2 + download de emails
│   ├── categorizer.py               # Motor de auto-categorizacion
│   ├── pipeline.py                  # Orquestador del flujo completo
│   └── task_runner.py               # ThreadPoolExecutor wrapper
│
├── web/                             # Interfaz web Flask
│   ├── __init__.py                  # App factory con blueprints
│   ├── routes/
│   │   ├── dashboard.py             # GET / - stats y acciones rapidas
│   │   ├── trips.py                 # GET/POST /trips - tabla con edicion htmx
│   │   ├── gmail.py                 # GET/POST /gmail - descarga de emails
│   │   ├── reports.py               # GET/POST /reports - summary, PDFs, pipeline
│   │   └── settings.py              # GET/POST /settings - config + reset
│   └── templates/
│       ├── base.html                # Layout: sidebar + Bootstrap 5 + htmx
│       ├── dashboard.html           # Cards de stats + desglose mensual
│       ├── trips.html               # Tabla con filtros y dropdowns inline
│       ├── gmail.html               # Estado Gmail + historial descargas
│       ├── reports.html             # Generacion de reportes y PDFs
│       ├── settings.html            # Direcciones + estado sistema + reset
│       ├── _trip_row.html           # Partial htmx: fila completa (swap outerHTML)
│       ├── _trip_row_content.html   # Partial: contenido interno de fila
│       ├── _alert.html              # Partial: alerta Bootstrap dismissible
│       └── _task_status.html        # Partial: spinner + polling htmx cada 2s
│
├── parser.py                        # Parser de emails Uber/Didi
├── main.py                          # Entry point CLI (backward compatible)
├── generar_reintegros.py            # Generador de PDFs (CSV o DB mode)
├── auto_categorize.py               # Wrapper legacy de services/categorizer
├── migrate_csv.py                   # Migracion unica CSV -> SQLite
├── run_web.py                       # Entry point web (abre browser en puerto 5100)
├── start_app.bat                    # Launcher Windows (cd correcto + python run_web.py)
├── requirements.txt                 # Dependencias Python
└── .gitignore                       # Excluye: credentials, token, DB, receipts, output
```

---

## 2. Logica de Negocio

### 2.1 Parsing de Recibos (`parser.py`)

**Deteccion de servicio** (en orden de prioridad):
1. Nombre del archivo (.eml) contiene "uber" o "didi"
2. Header `From` del email contiene "uber" o "didi"
3. Contenido HTML contiene "uber" o "didi"/"pone tu precio"

**Uber** - Extraccion por data-testid attributes:
- Monto: `data-testid="total_fare_amount"` -> regex `(ARS|USD|EUR)\s*\$?\s*([\d,]+\.?\d*)`
- Direcciones: `class="address-point-desc"` (indice 0=origen, 1=destino)
- Fecha: `email.utils.parsedate_to_datetime(date_str)` -> `.astimezone(UTC-3)` -> `%Y-%m-%d`
  - Fallback: `data-testid="payments_0_date_time"` (ya en hora local AR)

**Didi** - Extraccion por text parsing:
- Monto: Linea despues de "Total" -> regex `\$\s*([\d,]+\.?\d*)`
- Direcciones: Despues de patrones de hora `\d{1,2}:\d{2}\s*(?:am|pm)`, tomar lineas siguientes
- Fecha: Regex `(\d+)\s+(\w+)[,\s]+(\d{4})` con mapa de meses en espanol

**CRITICO - Timezone:** Uber envia emails con header `Date` en UTC (`+0000`). Argentina es UTC-3. Un viaje a las 22:00 AR tiene timestamp UTC del dia siguiente. Usar siempre `parsedate_to_datetime()` y convertir a AR antes de extraer la fecha. Si se stripea el timezone sin convertir, los viajes nocturnos quedan guardados con fecha incorrecta (+1 dia).

### 2.2 Categorizacion (`services/categorizer.py`)

**Regla de oro:** Si CUALQUIER direccion de trabajo aparece en origen O destino -> **Laburo**.

```
Prioridad 1: work_address en origin OR destination -> Laburo
Prioridad 2: home_address en origin OR destination (sin work) -> Personal
Prioridad 3: Ninguna coincidencia -> None (needs_review = 1)
```

**Normalizacion de direcciones** (`normalize_address()`):
- Lowercase
- Remover acentos: a/e/i/o/u/n
- Remover prefijos: "av.", "avenida", "calle", "gral.", "general"
- Remover todo despues de coma (ciudad, provincia)
- Colapsar espacios multiples

**Categorias manuales vs auto:** El flag `auto_categorized` controla si el pipeline puede sobreescribir:
- `auto_categorized = 1`: trip fue categorizado automaticamente, puede ser re-categorizado por el pipeline
- `auto_categorized = 0`: trip fue categorizado manualmente por el usuario, el pipeline lo **skipea**
- `update_trip_category()` siempre setea `auto_categorized = 0` para preservar la decision del usuario

**Direcciones de trabajo** se cargan desde `config/settings.json` (no versionado). Formato:
```
direccion normalizada 1     # Oficina principal
nombre de calle             # Matchea cualquier numero en esa calle
otra direccion 123          # Cliente
```
Ver `config/settings.example.json` para el formato esperado.

**Error critico a evitar:** Casa <-> Trabajo = **LABURO** (no Personal). Este error costaria dinero en reintegros perdidos.

### 2.3 Deduplicacion

**En modo DB:** Dos niveles de deduplicacion:
1. **Por filename:** `parse_all_receipts(use_db=True)` saltea archivos cuyo `filename` ya existe en la tabla `trips`. Previene re-parseo en cada pipeline run.
2. **Por contenido:** `UNIQUE(date, service, amount, origin, destination)` + `INSERT OR IGNORE`. Cubre casos donde el mismo viaje llega con distinto filename.

**En modo CSV legacy:** Key compuesta `date|service|amount|origin|destination`, `drop_duplicates(keep='first')`.

**CRITICO:** Si se corrigen fechas en la DB manualmente y despues se re-ejecuta el pipeline con el servidor Flask viejo en memoria (sin reiniciar), el parser viejo puede retornar fechas diferentes a las corregidas, bypasseando el UNIQUE constraint e insertando duplicados. **Siempre reiniciar el servidor despues de cambios en parser.py.**

### 2.4 Gmail API (`services/gmail_service.py`)

**Query de busqueda:**
```
subject:"Tu viaje" (from:noreply@uber.com OR from:didi@ar.didiglobal.com)
```

**Filtro post-descarga** (excluye promos que pasan el query):
- Keywords bloqueadas: "cuesta menos", "OFF", "descuento", "promo", "gratis", "regalo"

**Tracking:** Tabla `downloaded_emails` con `message_id` como PK evita re-descargas.

**Auth flow:** OAuth2 con scope `gmail.readonly`. Primera vez abre browser, despues auto-refresh via `token.json`.

**Filenames de .eml:** Generados desde el subject del email con `safe_subject` (solo alfanumerico + espacios). Subjects con no-breaking spaces (`\xa0`) producen palabras concatenadas (ej: `Tu viajeUber del...`). No afecta el parsing ya que la deteccion de servicio usa el header `From`, no el filename.

### 2.5 Generacion de PDFs (`generar_reintegros.py`)

**Batch mode:** Una sola instancia de Chromium para todos los PDFs.

**Skip de PDFs existentes:** Antes de generar cada PDF, verifica si ya existe en `reintegros/`. Si existe, lo omite. Parametro `force=True` para regenerar todos. En la web, checkbox "Regenerar todos (sobreescribir existentes)".

**Naming:** `{counter:02d}_{YYYYMMDD}_{service}_{currency}_{amount:.0f}.pdf`
- Counter es secuencial en orden cronologico. Si cambia la cantidad de Laburo trips (nuevos o reclasificados), los counters cambian y los PDFs viejos con counter incorrecto quedan huerfanos. Usar `force=True` despues de cambios de categorizacion.

**Settings PDF:** A4, margins 1cm, `print_background=True` para colores/imagenes.

**Playwright en background threads:** Funciona correctamente en `ThreadPoolExecutor`. Usar:
- `wait_until='domcontentloaded'` (no `networkidle`) para evitar bloqueos por recursos externos en el HTML del email
- `timeout=20000` (20s)
- `Path(pdf_path).absolute()` para evitar ambiguedad de CWD

---

## 3. Base de Datos

### 3.1 Schema

```sql
trips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    service         TEXT NOT NULL,           -- 'Uber' o 'Didi'
    date            TEXT NOT NULL,           -- formato YYYY-MM-DD (hora local AR, no UTC)
    origin          TEXT,
    destination     TEXT,
    amount          REAL NOT NULL,
    currency        TEXT DEFAULT 'ARS',
    category        TEXT DEFAULT '',         -- 'Laburo', 'Personal', o ''
    auto_categorized INTEGER DEFAULT 0,     -- 1=auto (pipeline puede sobreescribir), 0=manual (no tocar)
    needs_review    INTEGER DEFAULT 0,      -- 1 si necesita revision manual
    created_at      TEXT,
    updated_at      TEXT,
    UNIQUE(date, service, amount, origin, destination)
)

downloaded_emails (
    message_id      TEXT PRIMARY KEY,       -- Gmail message ID
    subject         TEXT,
    sender          TEXT,
    filename        TEXT,                   -- nombre del .eml guardado
    downloaded_at   TEXT DEFAULT (datetime('now'))
)

pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT DEFAULT (datetime('now')),
    finished_at     TEXT,
    status          TEXT,                   -- 'running', 'completed', 'error'
    emails_downloaded INTEGER,
    trips_parsed    INTEGER,
    duplicates_skipped INTEGER,
    trips_categorized INTEGER,
    pdfs_generated  INTEGER,
    error_message   TEXT
)

activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT,                   -- hora local (Python datetime.now())
    action_type     TEXT NOT NULL,          -- 'pipeline', 'gmail_download', 'generate_pdfs', etc.
    description     TEXT NOT NULL,          -- descripcion legible de la operacion
    status          TEXT DEFAULT 'success', -- 'success', 'error', 'warning'
    details         TEXT                    -- metadata opcional
)
```

### 3.2 Formato de Fechas

- **En DB:** `YYYY-MM-DD` en **hora local Argentina (UTC-3)**, no UTC
- **En CSV legacy:** `DD/MM/YYYY` (formato Excel español)
- **Migracion:** `migrate_csv.py` convierte DD/MM/YYYY -> YYYY-MM-DD

---

## 4. Interfaz Web

### 4.1 Rutas

| Metodo | Ruta | Funcion | Response |
|--------|------|---------|----------|
| GET | `/` | Dashboard con stats + registro de actividad | HTML completo |
| GET | `/trips/` | Lista de viajes con filtros | HTML completo |
| POST | `/trips/<id>/category` | Actualizar categoria | Partial `_trip_row.html` (htmx swap) |
| POST | `/trips/auto-categorize` | Auto-categorizar todos | HX-Redirect a /trips |
| POST | `/trips/export-csv` | Exportar DB a CSV | Partial `_alert.html` |
| GET | `/gmail/` | Estado Gmail + historial | HTML completo |
| POST | `/gmail/download` | Iniciar descarga background | Partial `_task_status.html` |
| GET | `/gmail/task-status/<id>` | Polling de progreso | Partial (alert o status) |
| GET | `/reports/` | Pagina de reportes | HTML completo |
| POST | `/reports/generate-summary` | Generar summary.md | Partial `_alert.html` |
| POST | `/reports/generate-pdfs` | Generar PDFs background | Partial `_task_status.html` |
| POST | `/reports/run-pipeline` | Pipeline completo background | Partial `_task_status.html` |
| GET | `/reports/task-status/<id>` | Polling de progreso | Partial (alert o status) |
| GET | `/settings/` | Configuracion | HTML completo |
| POST | `/settings/save` | Guardar direcciones | Partial `_alert.html` |
| POST | `/settings/reset` | Borrar todo y reiniciar | Partial `_alert.html` |

### 4.2 Patron htmx

La edicion inline de categorias usa htmx sin JavaScript custom:

```html
<select hx-post="/trips/{{ trip.id }}/category"
        hx-target="#trip-row-{{ trip.id }}"
        hx-swap="outerHTML"
        name="category">
```

Al cambiar el dropdown, htmx hace POST, el server devuelve la fila completa actualizada (`_trip_row.html`), y htmx reemplaza el `<tr>` entero.

### 4.3 Background Tasks

`task_runner.py` wrappea `ThreadPoolExecutor`. El patron es:
1. Route recibe POST, llama `task_runner.submit(func)` -> devuelve `task_id`
2. Response es `_task_status.html` con spinner + `hx-get` polling cada 2s
3. El polling endpoint chequea `task_runner.get_status(task_id)`
4. Cuando completa, devuelve `_alert.html` con resultado (htmx deja de pollear)

### 4.4 Puerto y Recarga

- **Puerto:** `5100` (definido en `run_web.py` y `start_app.bat`)
- **Auto-reload:** `debug=False` — el servidor **NO recarga automaticamente** al editar archivos Python. Despues de cualquier cambio de codigo, reiniciar el servidor (Ctrl+C + `start_app.bat`).

---

## 5. CLI - Modos de Uso

```bash
python main.py                  # v1 original: parse -> CSV (sin cambios)
python main.py --summary        # v1 original: CSV -> summary.md (sin cambios)
python main.py --db             # v2: parse -> SQLite
python main.py --summary --db   # v2: SQLite -> summary.md
python main.py --download       # v2: Gmail API -> receipts/*.eml
python main.py --pipeline       # v2: download + parse + categorize + summary + PDFs
python main.py --web            # v2: Flask en localhost:5100
python run_web.py               # v2: igual que --web (abre browser automaticamente)
python migrate_csv.py           # Migracion unica CSV -> SQLite
python auto_categorize.py       # v1: categorizar CSV directo
python auto_categorize.py --db  # v2: categorizar en SQLite
```

**Backward compatibility:** Sin flags, `main.py` se comporta identico a v1 (CSV puro, sin SQLite).

---

## 6. Problemas Conocidos y Soluciones

| Problema | Causa | Solucion |
|----------|-------|----------|
| CSV con separador `;` | Excel guarda con separador regional (ES) | Auto-deteccion en todos los scripts |
| Encoding errors en Windows | Caracteres Unicode en prints | Solo ASCII en stdout, `utf-8-sig` en archivos |
| WeasyPrint falla | Requiere GTK en Windows | Reemplazado por Playwright |
| Playwright lento con N PDFs | N instancias de browser | Batch mode: 1 browser para todos |
| Gmail descarga promos | Query `from:` es muy amplio | Filtro `subject:"Tu viaje"` + keywords anti-promo |
| "Alferez" vs "Alferez" (tilde) | Variaciones en direcciones | `normalize_address()` remueve acentos y prefijos |
| Viajes nocturnos con fecha +1 dia | Uber envia Date header en UTC; stripear TZ sin convertir | `parsedate_to_datetime()` + `.astimezone(UTC-3)` |
| Duplicados en DB tras fix de parser | Flask cached old parser; pipeline re-parseaba todos los .eml | `parse_all_receipts` skipea filenames ya en DB; reiniciar server tras cambios |
| Categorizacion manual sobreescrita | `update_trip_category` no reseteaba `auto_categorized` | Ahora setea `auto_categorized=0`; el pipeline respeta categorias manuales |
| PDFs faltantes en background thread | `networkidle` bloqueaba en recursos externos del HTML | Cambiado a `domcontentloaded` + timeout 20s + rutas absolutas |
| Counter de PDFs incorrecto tras cambios | Nuevos trips cambian el orden; PDFs viejos con numero viejo quedan huerfanos | Regenerar con `force=True` despues de reclasificaciones |

---

## 7. Guia para Claude (IA)

### Al retomar este proyecto:

1. **Leer primero:** Este archivo + `EJEMPLO_CATEGORIZACION.md`
2. **Regla critica:** Casa <-> Trabajo = **LABURO** (no Personal)
3. **Fuente de verdad:** `data/expense_tracker.db` (no el CSV)
4. **Config editable:** `config/settings.json` (direcciones de trabajo/casa)
5. **No romper backward compat:** `python main.py` sin flags = comportamiento v1
6. **Gmail requiere setup:** El usuario provee `config/credentials.json`
7. **htmx:** No se necesita JavaScript custom para la UI interactiva
8. **Fechas en DB:** Siempre `YYYY-MM-DD` en **hora local Argentina (UTC-3)**, no UTC
9. **`parser.py`:** `extract_html_from_eml()` (publica) wrappea `_extract_html_from_eml()` (privada)
10. **Playwright batch:** `convert_htmls_to_pdfs()` recibe lista de `(html, pdf_path)` tuples
11. **PDF skip:** `generate_reintegros(force=False)` omite PDFs existentes. Checkbox en web para forzar regeneracion
12. **Activity log:** `log_activity(action_type, description)` registra operaciones. Se muestra en Dashboard
13. **Timestamps:** `log_activity()` usa `datetime.now()` de Python (hora local), NO `datetime('now')` de SQLite (UTC)
14. **Testing:** NUNCA hacer POST a `/settings/save` o `/settings/reset` en tests automatizados (destruye datos reales)
15. **Flask no recarga:** `debug=False` — despues de editar cualquier .py, el usuario DEBE reiniciar el servidor para que los cambios tomen efecto. Siempre avisar esto.
16. **auto_categorized flag:** `0` = manual (pipeline no toca), `1` = auto (pipeline puede sobreescribir). `update_trip_category()` siempre setea a `0`.
17. **parse_all_receipts en DB mode:** Solo parsea archivos cuyo filename NO esta ya en `trips`. Idempotente por diseno.
18. **Puerto:** `5100` (no 5000)

---

**Repo:** https://github.com/jesusmendezb96/Analisis_Uber
