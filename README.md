# Analizador de Gastos de Uber/Didi

Sistema automatizado para procesar recibos de Uber y Didi desde Gmail, categorizarlos como gastos personales o laborales, y generar reportes para reintegros.

## Características

- ✅ Parsea recibos de **Uber** y **Didi** (archivos .eml)
- ✅ Extrae automáticamente: fecha, origen, destino, monto y moneda
- ✅ Detecta y elimina duplicados automáticamente
- ✅ Genera CSV para categorización manual
- ✅ Genera reporte Markdown con totales por categoría y mes
- ✅ **Convierte recibos HTML a PDF automáticamente** usando Playwright
- ✅ **Numera PDFs secuencialmente** para facilitar carga en formularios web
- ✅ Genera CSV listo para copiar al sistema de reintegros corporativo
- ✅ Maneja múltiples monedas (ARS, USD, EUR)

## Instalación

### 1. Requisitos

- Python 3.7 o superior
- pip (gestor de paquetes de Python)

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Las dependencias son:
- `beautifulsoup4` - Parsing de HTML
- `lxml` - Parser rápido
- `pandas` - Manipulación de datos y CSV
- `playwright` - Generación de PDFs con renderizado de navegador real

**Nota:** Playwright requiere una instalación adicional de binarios de navegador (Chromium), que se realiza con el segundo comando.

## Uso

### Paso 1: Descargar recibos de Gmail

1. Ve a Gmail y busca: `from:uber.receipts@uber.com` o `from:didi@ar.didiglobal.com`
2. Abre cada email de recibo
3. Descarga el email como .eml:
   - En Gmail web: Click en los 3 puntos → "Descargar mensaje"
   - O usa `Ctrl+S` → "Guardar como" → Tipo: "Correo electrónico"
4. Coloca todos los archivos .eml en la carpeta `receipts/`

### Paso 2: Parsear recibos y generar CSV

```bash
python main.py
```

Esto generará `output/uber_trips.csv` con todos los viajes parseados.

**Salida esperada:**
```
Found 5 receipt files

[OK] Tu viaje del jueves con Uber.eml
[OK] Tu viaje del viernes con Uber.eml
[OK] Tu viaje Poné Tu Precio.eml
...

[OK] Successfully parsed: 5 trips
[OK] Generated: output\uber_trips.csv
```

### Paso 3: Categorizar viajes

1. Abre `output/uber_trips.csv` en Excel o un editor de texto
2. Llena la columna `Category` con:
   - `Personal` - para viajes personales
   - `Laburo` - para viajes de trabajo
3. Guarda el archivo

**Ejemplo:**
```csv
filename,service,date,origin,destination,amount,currency,Category
viaje_1.eml,Uber,2026-01-23,Av. Corrientes 1234,Av. Libertador 5678,5938.0,ARS,Personal
viaje_2.eml,Uber,2026-01-24,Oficina Central,Cliente XYZ,6344.0,ARS,Laburo
```

### Paso 4: Generar resumen

```bash
python main.py --summary
```

Esto genera `output/summary.md` con totales por categoría y mes.

**Salida esperada:**
```
============================================================
EXPENSE SUMMARY
============================================================
Laburo: ARS 47,233.34 (3 trips)
Personal: ARS 13,437.00 (2 trips)
------------------------------------------------------------
2026-02: ARS 20,201.00
2026-01: ARS 40,469.34
============================================================
```

### Paso 5: Generar archivos para reintegro (opcional)

Si necesitas presentar reintegros corporativos, este paso automatiza la generación de PDFs:

```bash
python generar_reintegros.py
```

**Esto generará:**
- ✅ PDFs automáticamente en `reintegros/` (ej: `01_20260105_Uber_ARS_24757.pdf`)
  - Numerados secuencialmente (01, 02, 03...) en orden cronológico
  - Facilita la carga ordenada en formularios web
- ✅ HTMLs de respaldo en `reintegros/recibos_html/`
- ✅ CSV listo para copiar en `reintegros/reintegro_data.csv`
- ✅ Archivo de instrucciones en `reintegros/INSTRUCCIONES.txt`

**Salida esperada:**
```
======================================================================
GENERADOR DE REINTEGROS
======================================================================

Viajes de Laburo encontrados: 10
Monto total a reintegrar: ARS 179,859.34

Procesando: Tu viaje Uber del lunes.eml
  [OK] HTML guardado: 01_20260105_Uber_ARS_24757.html
  Generando PDF...
  [OK] PDF generado: 01_20260105_Uber_ARS_24757.pdf
...

======================================================================
RESUMEN
======================================================================
[OK] PDFs generados: 10
[OK] HTMLs guardados (backup): 10
[OK] CSV generado: reintegros\reintegro_data.csv
[OK] Instrucciones: reintegros\INSTRUCCIONES.txt

Total a reintegrar: ARS 179,859.34
======================================================================
```

**Nota:** La primera vez que ejecutes este script, Playwright se instalará automáticamente si no está presente.

## Estructura del Proyecto

```
Analisis_Uber/
├── receipts/                # Coloca tus archivos .eml aquí
│   ├── .gitkeep
│   └── (tus archivos .eml)
├── output/                  # Reportes generados
│   ├── uber_trips.csv       # CSV con todos los viajes (EDITAR CATEGORÍAS AQUÍ)
│   └── summary.md           # Resumen con totales
├── reintegros/              # Archivos para reintegro corporativo
│   ├── 01_*.pdf             # PDFs numerados secuencialmente
│   ├── 02_*.pdf
│   ├── ...
│   ├── recibos_html/        # HTMLs de respaldo
│   ├── reintegro_data.csv   # Datos listos para copiar al formulario
│   └── INSTRUCCIONES.txt    # Guía de carga
├── parser.py                # Lógica de parsing Uber/Didi
├── main.py                  # Script principal
├── generar_reintegros.py    # Generador de PDFs y CSV de reintegro
├── auto_categorize.py       # Auto-categorización (opcional)
├── requirements.txt         # Dependencias
├── README.md                # Este archivo (guía de usuario)
├── CLAUDE.md                # Directivas técnicas (para desarrollo)
├── EJEMPLO_CATEGORIZACION.md # Reglas de categorización validadas
└── .gitignore               # Archivos ignorados por git
```

## Formato del CSV

El archivo `output/uber_trips.csv` contiene:

| Columna | Descripción | Ejemplo |
|---------|-------------|---------|
| filename | Nombre del archivo .eml | `Tu viaje del lunes.eml` |
| service | Servicio usado | `Uber` o `Didi` |
| date | Fecha del viaje | `2026-01-23` |
| origin | Dirección de origen | `Av. Corrientes 1234, CABA` |
| destination | Dirección de destino | `Av. Libertador 5678, CABA` |
| amount | Monto pagado | `5938.0` |
| currency | Moneda | `ARS`, `USD`, `EUR` |
| Category | Categoría (manual) | `Personal` o `Laburo` |

## Formato del Resumen

El archivo `output/summary.md` incluye:

- **Totales generales** por categoría
- **Desglose por servicio** (Uber vs Didi)
- **Desglose mensual** con subtotales

Ejemplo:
```markdown
# Uber/Didi Expense Summary

## Overall Totals by Category
- **Laburo**: ARS 47,233.34 (3 trips)
- **Personal**: ARS 13,437.00 (2 trips)

## By Service
- **Uber**: ARS 39,982.00 (4 trips)
- **Didi**: ARS 20,688.34 (1 trips)

## Monthly Breakdown
### 2026-02
- **Laburo**: ARS 20,201.00 (1 trips)
- *Month Total*: ARS 20,201.00 (1 trips)
```

## Formato de Archivos de Reintegro

Cuando ejecutas `python generar_reintegros.py`, se generan archivos listos para cargar en el sistema de reintegros corporativo.

### Estructura de archivos PDF

Los PDFs se nombran siguiendo este formato:
```
XX_YYYYMMDD_Servicio_MONEDA_MONTO.pdf

Ejemplo: 01_20260105_Uber_ARS_24757.pdf
```

Donde:
- **XX** = Prefijo numérico secuencial (01, 02, 03...) en orden cronológico
- **YYYYMMDD** = Fecha del viaje (año-mes-día)
- **Servicio** = Uber o Didi
- **MONEDA** = ARS, USD, EUR, etc.
- **MONTO** = Monto sin decimales

**Ventaja:** Los archivos están pre-ordenados para facilitar la carga secuencial en formularios web.

### CSV de Reintegro

El archivo `reintegros/reintegro_data.csv` contiene:

| Columna | Descripción | Ejemplo |
|---------|-------------|---------|
| Fecha | Fecha del viaje | `05/01/2026` |
| Tipo_Gasto | Tipo de gasto | `Taxi` |
| Servicio | Servicio usado | `Uber` o `Didi` |
| Monto | Monto a reintegrar | `24757.00` |
| Moneda | Moneda | `ARS` |
| Archivo_PDF | Nombre del PDF | `01_20260105_Uber_ARS_24757.pdf` |
| Origen | Dirección de origen | `Alferez Hipólito Bouchard...` |
| Destino | Dirección de destino | `Av. Juan Bautista Alberdi...` |

**Uso:** Copia y pega directamente desde este CSV al formulario web de reintegros de tu empresa.

## Resolución de Problemas

### No se parsean los recibos

- Verifica que los archivos están en formato .eml
- Asegúrate de que son recibos reales de Uber o Didi
- Revisa que los archivos no estén corruptos

### Datos incorrectos

- El parser se basa en la estructura actual de los emails de Uber/Didi
- Si Uber o Didi cambian el formato de sus emails, el parser puede necesitar ajustes
- Reporta problemas con ejemplos de recibos

### Encoding issues en Windows

- Los archivos CSV usan UTF-8 con BOM para compatibilidad con Excel
- Si ves caracteres raros, abre el CSV en un editor que soporte UTF-8

### Error al generar PDFs

**Problema:** `Playwright no está instalado`

**Solución:**
```bash
pip install playwright
python -m playwright install chromium
```

**Problema:** PDFs generados están en blanco o con errores

**Solución:**
- Verifica que los archivos .eml tienen contenido HTML válido
- Ejecuta el script nuevamente (la primera vez puede haber errores de instalación)
- Revisa que Chromium se instaló correctamente en: `%USERPROFILE%\AppData\Local\ms-playwright\`

### Separador de CSV incorrecto

**Problema:** Excel muestra todo en una columna

**Solución:**
- El script detecta automáticamente el separador (`,` o `;`)
- Si editaste el CSV en Excel, puede haber cambiado el separador a `;` (configuración regional)
- Esto es normal y el script lo maneja automáticamente

## Privacidad y Seguridad

- ⚠️ Los archivos de recibos contienen información personal y financiera
- Los archivos `.eml` y los reportes generados están en `.gitignore`
- **No subas recibos reales a repositorios públicos**
- Este proyecto NO almacena ni transmite datos a servicios externos

## Mejoras Implementadas

- ✅ Conversión automática HTML → PDF con Playwright
- ✅ Numeración secuencial de archivos para formularios web
- ✅ Generación de CSV listo para sistema de reintegros
- ✅ Detección y eliminación de duplicados
- ✅ Soporte para Uber y Didi
- ✅ Categorización automática basada en direcciones (opcional)

## Próximas Mejoras Potenciales

- [ ] Automatización de descarga desde Gmail (OAuth/IMAP)
- [ ] Soporte para múltiples monedas con conversión automática
- [ ] Interfaz web para categorización
- [ ] Tests automatizados
- [ ] Exportar a Excel con formato personalizado

## Contribuir

Para reportar bugs o sugerir mejoras, por favor crea un issue con:
- Descripción del problema
- Ejemplo de recibo (con datos sensibles removidos)
- Output esperado vs actual

## Licencia

Este proyecto es de uso personal. Usar bajo tu propio riesgo.
