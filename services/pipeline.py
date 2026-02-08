#!/usr/bin/env python3
"""
Unified pipeline orchestrator.
Runs the full flow: Gmail download -> Parse -> Deduplicate -> Categorize -> Summary -> PDFs
"""
from datetime import datetime
from pathlib import Path


def run_full_pipeline(download_gmail=False, after_date=None, task_id=None):
    """
    Run the full automated pipeline.

    Args:
        download_gmail: Whether to download from Gmail first (requires credentials)
        after_date: Only download emails after this date (YYYY-MM-DD)
        task_id: Optional task_id for progress reporting

    Returns:
        dict with full execution stats
    """
    from services.database import init_db, start_pipeline_run, finish_pipeline_run

    init_db()
    run_id = start_pipeline_run()

    stats = {
        'emails_downloaded': 0,
        'trips_parsed': 0,
        'duplicates_skipped': 0,
        'trips_categorized': 0,
        'pdfs_generated': 0,
    }

    try:
        print("="*70)
        print("PIPELINE AUTOMATIZADO - Uber/Didi Expense Analyzer")
        print("="*70)

        # Step 1: Download from Gmail (optional)
        if download_gmail:
            print("\n--- PASO 1: Descarga de Gmail ---")
            try:
                from services.gmail_service import download_new_receipts, is_configured
                if is_configured():
                    gmail_stats = download_new_receipts(after_date=after_date)
                    stats['emails_downloaded'] = gmail_stats.get('downloaded', 0)
                else:
                    print("[!] Gmail no configurado. Saltando descarga.")
                    print("    Para configurar: ver SETUP_GMAIL.md")
            except Exception as e:
                print(f"[X] Error en descarga Gmail: {e}")
                print("    Continuando con recibos existentes...")
        else:
            print("\n--- PASO 1: Descarga de Gmail (saltado) ---")

        # Step 2: Parse .eml files
        print("\n--- PASO 2: Parseo de recibos ---")
        from main import parse_all_receipts
        result = parse_all_receipts(use_db=True)
        if result:
            stats['trips_parsed'] = result.get('inserted', 0)
            stats['duplicates_skipped'] = result.get('duplicates', 0)

        # Step 3: Auto-categorize
        print("\n--- PASO 3: Auto-categorizacion ---")
        from services.categorizer import categorize_all_trips
        cat_stats = categorize_all_trips()
        stats['trips_categorized'] = cat_stats['categorized']
        print(f"[OK] Categorizados: {cat_stats['categorized']} viajes")
        print(f"     - Laburo: {cat_stats['work']}")
        print(f"     - Personal: {cat_stats['personal']}")
        if cat_stats['needs_review'] > 0:
            print(f"[!] Necesitan revision manual: {cat_stats['needs_review']}")

        # Step 4: Generate summary
        print("\n--- PASO 4: Generacion de reporte ---")
        from main import generate_summary
        generate_summary(use_db=True)

        # Step 5: Generate PDFs
        print("\n--- PASO 5: Generacion de PDFs ---")
        from generar_reintegros import generate_reintegros
        pdf_result = generate_reintegros(use_db=True, task_id=task_id)
        stats['pdfs_generated'] = pdf_result.get('pdfs_generated', 0)
        stats['pdfs_skipped'] = pdf_result.get('pdfs_skipped', 0)

        # Final summary
        print("\n" + "="*70)
        print("PIPELINE COMPLETADO")
        print("="*70)
        print(f"  Emails descargados: {stats['emails_downloaded']}")
        print(f"  Viajes parseados: {stats['trips_parsed']}")
        print(f"  Duplicados ignorados: {stats['duplicates_skipped']}")
        print(f"  Viajes categorizados: {stats['trips_categorized']}")
        print(f"  PDFs generados: {stats['pdfs_generated']}")
        if stats.get('pdfs_skipped', 0) > 0:
            print(f"  PDFs ya existentes (omitidos): {stats['pdfs_skipped']}")
        print("="*70)

        finish_pipeline_run(run_id, stats)

        from services.database import log_activity
        log_activity('pipeline',
                     f'Pipeline completado: {stats["trips_parsed"]} viajes, {stats["pdfs_generated"]} PDFs')

    except Exception as e:
        print(f"\n[X] Error en pipeline: {e}")
        finish_pipeline_run(run_id, stats, error=str(e))

        from services.database import log_activity
        log_activity('pipeline', f'Error en pipeline: {e}', status='error')

        raise

    return stats
