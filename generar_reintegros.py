#!/usr/bin/env python3
"""
Generador de Reintegros - Uber/Didi
Extrae recibos HTML y genera CSV con datos listos para el formulario de reintegros.
Supports both CSV and SQLite database modes.
"""
import pandas as pd
from pathlib import Path
from parser import _extract_html_from_eml
from datetime import datetime


def _ensure_playwright():
    """Check if Playwright is available, try to install if not."""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        print("\n[!] Playwright no esta instalado.")
        print("    Instalando playwright...")
        try:
            import subprocess
            import sys
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'],
                         check=True, capture_output=True)
            subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'],
                         check=True)
            print("    [OK] Instalado. Ejecuta el script de nuevo.")
        except Exception as e:
            print(f"    [X] Error instalando: {e}")
            print("    Ejecuta manualmente:")
            print("      python -m pip install playwright")
            print("      python -m playwright install chromium")
        return False


def convert_htmls_to_pdfs(html_pdf_pairs, task_id=None):
    """
    Convert multiple HTMLs to PDFs using a single browser instance.

    Args:
        html_pdf_pairs: list of (html_content, pdf_path) tuples
        task_id: optional task_id for progress reporting

    Returns:
        Number of successful conversions
    """
    if not _ensure_playwright():
        return 0

    from playwright.sync_api import sync_playwright

    success_count = 0
    total = len(html_pdf_pairs)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for i, (html_content, pdf_path) in enumerate(html_pdf_pairs):
                try:
                    page.set_content(html_content, wait_until='networkidle')
                    page.pdf(
                        path=str(pdf_path),
                        format='A4',
                        margin={'top': '1cm', 'right': '1cm', 'bottom': '1cm', 'left': '1cm'},
                        print_background=True,
                    )
                    success_count += 1
                except Exception as e:
                    print(f"  [X] Error generando PDF {pdf_path.name}: {e}")

                # Report progress
                if task_id:
                    from services import task_runner
                    progress = int((i + 1) / total * 100)
                    task_runner.update_progress(task_id, progress, f"PDF {i+1}/{total}")

            browser.close()

    except Exception as e:
        print(f"[X] Error con Playwright: {e}")

    return success_count


def _parse_date_flexible(date_str):
    """Parse date from various formats into a datetime object."""
    if not date_str or str(date_str) == 'nan':
        return None

    date_str = str(date_str).strip()

    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    try:
        return pd.to_datetime(date_str)
    except Exception:
        return None


def generate_reintegros(use_db=False, task_id=None):
    """
    Main function to generate reintegro PDFs and CSV.

    Args:
        use_db: If True, read trips from SQLite database
        task_id: Optional task_id for progress reporting
    """
    # Load trips
    if use_db:
        from services.database import get_all_trips
        rows = get_all_trips(category_filter='Laburo')
        if not rows:
            print("[!] No hay viajes categorizados como 'Laburo' en la base de datos")
            return {'pdfs_generated': 0}

        laburo_trips = []
        for row in rows:
            laburo_trips.append({
                'filename': row['filename'],
                'service': row['service'],
                'date': row['date'],
                'origin': row['origin'],
                'destination': row['destination'],
                'amount': row['amount'],
                'currency': row['currency'],
            })
    else:
        csv_path = Path('output/uber_trips.csv')
        if not csv_path.exists():
            print("[X] Error: output/uber_trips.csv no encontrado")
            print("    Ejecuta primero: python main.py")
            return {'pdfs_generated': 0}

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            separator = ';' if ';' in first_line else ','

        df = pd.read_csv(csv_path, sep=separator, encoding='utf-8-sig')
        df_laburo = df[df['Category'] == 'Laburo'].copy()

        if len(df_laburo) == 0:
            print("[!] No hay viajes categorizados como 'Laburo'")
            return {'pdfs_generated': 0}

        laburo_trips = df_laburo.to_dict('records')

    # Sort by date (oldest first)
    laburo_trips.sort(key=lambda t: _parse_date_flexible(t['date']) or datetime.min)

    total_amount = sum(float(t['amount']) for t in laburo_trips)

    print(f"\n{'='*70}")
    print(f"GENERADOR DE REINTEGROS")
    print(f"{'='*70}")
    print(f"\nViajes de Laburo encontrados: {len(laburo_trips)}")
    print(f"Monto total a reintegrar: ARS {total_amount:,.2f}\n")

    # Create directories
    reintegros_dir = Path('reintegros')
    reintegros_dir.mkdir(exist_ok=True)
    htmls_dir = reintegros_dir / 'recibos_html'
    htmls_dir.mkdir(exist_ok=True)

    receipts_dir = Path('receipts')
    reintegro_data = []
    html_pdf_pairs = []

    for counter, trip in enumerate(laburo_trips, start=1):
        filename = trip['filename']
        eml_path = receipts_dir / filename

        if not eml_path.exists():
            print(f"[!] Archivo no encontrado: {filename}")
            continue

        # Parse date
        date_obj = _parse_date_flexible(trip['date'])
        if date_obj:
            date_str = date_obj.strftime('%Y%m%d')
            date_display = date_obj.strftime('%d/%m/%Y')
        else:
            date_str = 'FECHA'
            date_display = str(trip['date'])

        service = trip['service']
        amount = float(trip['amount'])
        currency = trip.get('currency', 'ARS')

        prefix = f"{counter:02d}"
        html_filename = f"{prefix}_{date_str}_{service}_{currency}_{amount:.0f}.html"
        pdf_filename = f"{prefix}_{date_str}_{service}_{currency}_{amount:.0f}.pdf"

        html_path = htmls_dir / html_filename
        pdf_path = reintegros_dir / pdf_filename

        # Extract HTML
        print(f"Procesando: {filename}")
        html_content, _ = _extract_html_from_eml(eml_path)

        if html_content:
            # Save HTML backup
            try:
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"  [OK] HTML guardado: {html_filename}")
            except Exception as e:
                print(f"  [!] Advertencia - no se pudo guardar HTML: {e}")

            # Queue for batch PDF conversion
            html_pdf_pairs.append((html_content, pdf_path))

            # Prepare reintegro data
            origin_str = str(trip.get('origin', ''))
            dest_str = str(trip.get('destination', ''))
            reintegro_data.append({
                'Fecha': date_display,
                'Tipo_Gasto': 'Taxi',
                'Servicio': service,
                'Monto': f"{amount:.2f}",
                'Moneda': currency,
                'Archivo_PDF': pdf_filename,
                'Origen': origin_str[:60] + '...' if len(origin_str) > 60 else origin_str,
                'Destino': dest_str[:60] + '...' if len(dest_str) > 60 else dest_str,
            })
        else:
            print(f"  [X] No se pudo extraer HTML")

    # Batch convert all HTMLs to PDFs (single browser instance)
    if html_pdf_pairs:
        print(f"\nGenerando {len(html_pdf_pairs)} PDFs...")
        pdf_count = convert_htmls_to_pdfs(html_pdf_pairs, task_id=task_id)
        print(f"[OK] {pdf_count} PDFs generados exitosamente")
    else:
        pdf_count = 0

    # Generate CSV and instructions
    if reintegro_data:
        reintegro_df = pd.DataFrame(reintegro_data)

        csv_output = reintegros_dir / 'reintegro_data.csv'
        reintegro_df.to_csv(csv_output, index=False, encoding='utf-8-sig', sep=';')

        # Create instructions file
        instructions_file = reintegros_dir / 'INSTRUCCIONES.txt'
        with open(instructions_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("INSTRUCCIONES PARA CARGAR REINTEGROS\n")
            f.write("="*70 + "\n\n")
            f.write("Los PDFs ya fueron generados automaticamente!\n\n")
            f.write("PASO 1: Revisar PDFs generados\n")
            f.write("-"*70 + "\n")
            f.write("1. Los PDFs estan en la carpeta: reintegros/\n")
            f.write("2. Puedes abrirlos para verificar que se ven bien\n")
            f.write("3. Los HTMLs originales estan en: reintegros/recibos_html/\n\n")
            f.write("PASO 2: Cargar en el sistema de reintegros\n")
            f.write("-"*70 + "\n")
            f.write("1. Abre el archivo: reintegros/reintegro_data.csv\n")
            f.write("2. Para cada fila en el CSV:\n")
            f.write("   - Campo FECHA: copia de la columna 'Fecha'\n")
            f.write("   - Campo TIPO DE GASTO: selecciona 'Taxi'\n")
            f.write("   - Campo MONTO: copia de la columna 'Monto'\n")
            f.write("   - Campo ARCHIVO: sube el PDF correspondiente\n\n")
            f.write(f"RESUMEN:\n")
            f.write(f"  Total de viajes: {len(reintegro_df)}\n")
            f.write(f"  Monto total: ARS {reintegro_df['Monto'].astype(float).sum():,.2f}\n\n")
            f.write("="*70 + "\n")

        print(f"\n{'='*70}")
        print(f"RESUMEN")
        print(f"{'='*70}")
        print(f"[OK] PDFs generados: {pdf_count}")
        print(f"[OK] HTMLs guardados (backup): {len(reintegro_data)}")
        print(f"[OK] CSV generado: {csv_output}")
        print(f"[OK] Instrucciones: {instructions_file}")
        print(f"\nTotal a reintegrar: ARS {reintegro_df['Monto'].astype(float).sum():,.2f}")
        print(f"\nArchivos en: {reintegros_dir.absolute()}/")
        print(f"\n{'='*70}")
        print("PROXIMOS PASOS:")
        print("1. Revisa los PDFs generados en: reintegros/")
        print(f"   - Los archivos estan numerados en orden cronologico (01, 02, 03...)")
        print(f"   - Los HTMLs originales estan en: {htmls_dir.absolute()}/")
        print("")
        print("2. Lee el archivo INSTRUCCIONES.txt para mas detalles")
        print("")
        print("3. Usa reintegro_data.csv para copiar/pegar datos al formulario web")
        print(f"{'='*70}")

        # Preview
        print("\n Vista previa de datos para reintegro:")
        print("-" * 70)
        preview_df = reintegro_df[['Fecha', 'Tipo_Gasto', 'Monto', 'Archivo_PDF']].head(10)
        for _, row in preview_df.iterrows():
            print(f"{row['Fecha']:12} | {row['Tipo_Gasto']:8} | ARS {row['Monto']:>10} | {row['Archivo_PDF']}")
        if len(reintegro_df) > 10:
            print(f"... y {len(reintegro_df) - 10} mas en el CSV")
        print("-" * 70)
    else:
        print("\n[!] No se generaron archivos. Revisa los errores arriba.")

    return {'pdfs_generated': pdf_count, 'total_amount': total_amount}


if __name__ == '__main__':
    generate_reintegros()
