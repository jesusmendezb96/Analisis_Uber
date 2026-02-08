# Analizador de Gastos Uber/Didi

Sistema automatizado para procesar recibos de Uber y Didi, categorizarlos como gastos laborales o personales, y generar archivos listos para reintegros corporativos.

Incluye interfaz web local, integracion con Gmail API para descarga automatica, y auto-categorizacion inteligente por direcciones.

## Funcionalidades

- **Descarga automatica** de recibos desde Gmail via API (OAuth2)
- **Parsing** de emails .eml de Uber y Didi (fecha, origen, destino, monto, moneda)
- **Deduplicacion automatica** via constraints de base de datos
- **Auto-categorizacion** de viajes (Laburo/Personal) basada en direcciones configurables
- **Interfaz web** local con Bootstrap + htmx para revision y edicion de categorias
- **Generacion de PDFs** con Playwright (Chromium headless, batch optimizado, skip de existentes)
- **Registro de actividad** en el dashboard con historial de todas las operaciones
- **Pipeline unificado** que ejecuta todo el flujo con un click o un comando
- **CLI backward-compatible** con el flujo manual original

## Instalacion

### Requisitos

- Python 3.10 o superior
- pip

### Dependencias

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Las dependencias principales son:

| Paquete | Uso |
|---------|-----|
| beautifulsoup4 | Parsing de HTML de recibos |
| lxml | Backend de parsing |
| pandas | Manipulacion de datos y CSV |
| playwright | Generacion de PDFs con renderizado real de browser |
| flask | Interfaz web local |
| google-api-python-client | Integracion Gmail API (opcional) |

### Gmail API (opcional)

Para habilitar la descarga automatica desde Gmail:

1. Ir a [Google Cloud Console](https://console.cloud.google.com)
2. Crear un proyecto y habilitar la **Gmail API**
3. Crear credenciales **OAuth 2.0** (tipo "App de escritorio")
4. Descargar el JSON y guardarlo como `config/credentials.json`
5. La primera ejecucion abre el navegador para autorizar (scope: solo lectura)
6. El token se guarda automaticamente en `config/token.json`

## Uso

### Opcion A: Interfaz Web (Recomendada)

```bash
python main.py --web
```

Abre http://localhost:5000 con:

- **Dashboard** - Estadisticas generales, desglose por mes, registro de actividad
- **Viajes** - Tabla completa con edicion inline de categorias (dropdown por fila)
- **Gmail** - Descargar recibos con selector de fecha
- **Reportes** - Generar summary, PDFs (con skip de existentes), o ejecutar pipeline completo
- **Configuracion** - Editar direcciones de trabajo/casa, resetear datos

### Opcion B: Pipeline automatizado por CLI

```bash
python main.py --pipeline
```

Ejecuta en secuencia: parseo de recibos -> deduplicacion -> auto-categorizacion -> reporte -> PDFs.

Agregar `--download` para incluir descarga de Gmail:

```bash
python main.py --pipeline --download
```

### Opcion C: Flujo manual (CLI original)

```bash
# 1. Colocar archivos .eml en receipts/
python main.py                  # Parsear y generar CSV

# 2. Abrir output/uber_trips.csv en Excel, llenar columna Category

python main.py --summary        # Generar reporte
python generar_reintegros.py    # Generar PDFs de reintegro
```

## Comandos CLI

| Comando | Descripcion |
|---------|-------------|
| `python main.py` | Parsear recibos y generar CSV (modo original) |
| `python main.py --summary` | Generar summary desde CSV categorizado |
| `python main.py --db` | Parsear recibos y guardar en SQLite |
| `python main.py --summary --db` | Generar summary desde base de datos |
| `python main.py --download` | Descargar recibos nuevos de Gmail |
| `python main.py --pipeline` | Pipeline completo automatizado |
| `python main.py --web` | Lanzar interfaz web en localhost:5000 |
| `python run_web.py` | Lanzar web (abre browser automaticamente) |
| `python migrate_csv.py` | Migrar CSV existente a SQLite (una sola vez) |
| `python auto_categorize.py` | Auto-categorizar CSV directo |
| `python auto_categorize.py --db` | Auto-categorizar en base de datos |

## Arquitectura

### Flujo de Datos

```
Gmail API ──> receipts/*.eml ──> parser.py ──> SQLite DB ──> categorizer.py
                                                  │
                                    ┌─────────────┼─────────────┐
                                    v             v             v
                              summary.md    reintegros/*.pdf  Web UI
                                           reintegro_data.csv
```

### Estructura del Proyecto

```
Analisis_Uber/
├── config/                     # Configuracion
│   ├── credentials.json        # Gmail OAuth (no versionado)
│   ├── token.json              # Token auto-generado (no versionado)
│   └── settings.json           # Direcciones de trabajo/casa
│
├── data/                       # Base de datos SQLite (no versionado)
├── services/                   # Logica de negocio
│   ├── database.py             # Schema + queries SQLite
│   ├── gmail_service.py        # Gmail API OAuth + descarga
│   ├── categorizer.py          # Auto-categorizacion por direcciones
│   ├── pipeline.py             # Orquestador del flujo completo
│   └── task_runner.py          # Ejecutor de tareas background
│
├── web/                        # Interfaz web Flask
│   ├── routes/                 # 5 blueprints: dashboard, trips, gmail, reports, settings
│   └── templates/              # Jinja2 + Bootstrap 5 + htmx
│
├── parser.py                   # Parser de recibos Uber/Didi
├── main.py                     # Entry point CLI
├── generar_reintegros.py       # Generador de PDFs
├── auto_categorize.py          # Categorizacion (wrapper legacy)
├── migrate_csv.py              # Migracion CSV -> SQLite
└── run_web.py                  # Entry point web
```

### Base de Datos

SQLite con WAL mode. Cuatro tablas:

- **trips** - Viajes con deduplicacion `UNIQUE(date, service, amount, origin, destination)`
- **downloaded_emails** - Tracking de emails descargados (evita re-descargas)
- **pipeline_runs** - Historial de ejecuciones del pipeline
- **activity_log** - Registro de todas las operaciones (visible en Dashboard)

Fechas almacenadas como `YYYY-MM-DD` (ISO 8601).

## Logica de Categorizacion

### Regla Principal

Un viaje es **Laburo** si el origen O el destino contiene cualquier direccion de trabajo configurada. Esto incluye viajes Casa -> Trabajo y Trabajo -> Casa.

Un viaje es **Personal** solo si NO involucra ninguna direccion de trabajo.

### Direcciones Configurables

Las direcciones se configuran en `config/settings.json` o desde la web UI en `/settings`:

```json
{
    "work_addresses": [
        "av. corrientes 1234",
        "calle oficina 567"
    ],
    "home_address": "mi casa 890"
}
```

Copiar `config/settings.example.json` a `config/settings.json` y completar con las direcciones reales. Las direcciones se normalizan automaticamente: lowercase, sin acentos, sin prefijos (Av., Avenida, Calle).

## Archivos de Reintegro

Al generar PDFs, se crean en `reintegros/`:

| Archivo | Contenido |
|---------|-----------|
| `01_20260105_Uber_ARS_24757.pdf` | PDF del recibo (numerado cronologicamente) |
| `recibos_html/*.html` | HTMLs de respaldo |
| `reintegro_data.csv` | CSV con datos para copiar al formulario corporativo |
| `INSTRUCCIONES.txt` | Guia de carga paso a paso |

Formato de nombre PDF: `{numero}_{YYYYMMDD}_{servicio}_{moneda}_{monto}.pdf`

El CSV de reintegro incluye: Fecha, Tipo_Gasto, Servicio, Monto, Moneda, Archivo_PDF, Origen, Destino.

## Resolucion de Problemas

| Problema | Solucion |
|----------|----------|
| Excel muestra CSV en una sola columna | El sistema auto-detecta separador `,` o `;`. Abrir con "Datos > Desde texto" |
| Caracteres raros en terminal Windows | Los archivos usan UTF-8 con BOM. Solo afecta la visualizacion en consola |
| Playwright no instalado | `pip install playwright && python -m playwright install chromium` |
| Gmail descarga emails que no son recibos | El filtro usa `subject:"Tu viaje"` + keywords anti-promo. Verificar en `/settings` |
| Direccion de trabajo no reconocida | Agregar en `config/settings.json` o desde la web en `/settings` (normalizada, sin acentos) |
| PDFs no se regeneran al presionar "Generar PDFs" | Los PDFs existentes se omiten automaticamente. Marcar "Regenerar todos" para forzar |

## Privacidad y Seguridad

- Las credenciales de Gmail (`credentials.json`, `token.json`) estan excluidas del repositorio
- Los recibos (.eml), base de datos, y archivos generados no se versionan
- Gmail API se usa con scope `readonly` (solo lectura)
- El sistema corre localmente, no transmite datos a servicios externos
- La interfaz web solo escucha en `127.0.0.1` (localhost)

## Tecnologias

Python 3.10+ | Flask | SQLite | htmx | Bootstrap 5 | Playwright | Gmail API

## Licencia

Proyecto de uso personal.
