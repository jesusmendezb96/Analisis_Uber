#!/usr/bin/env python3
"""
One-time migration: CSV -> SQLite database.
Reads output/uber_trips.csv and imports all trips preserving existing categories.
"""
from pathlib import Path
from datetime import datetime
from services.database import init_db, upsert_trip_with_category, get_all_trips


def normalize_date(date_str):
    """
    Normalize date to YYYY-MM-DD format.
    Handles: DD/MM/YYYY, YYYY-MM-DD, D/M/YYYY
    """
    if not date_str or str(date_str) == 'nan':
        return None

    date_str = str(date_str).strip()

    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue

    return date_str


def migrate():
    """Run the CSV to SQLite migration."""
    csv_path = Path('output/uber_trips.csv')

    if not csv_path.exists():
        print("[X] Error: output/uber_trips.csv no encontrado")
        print("    No hay datos para migrar.")
        return False

    # Auto-detect separator
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        first_line = f.readline()
        separator = ';' if ';' in first_line else ','

    import csv
    trips = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=separator)
        for row in reader:
            trips.append(row)

    if not trips:
        print("[!] CSV esta vacio, nada que migrar.")
        return False

    print(f"[OK] Leidos {len(trips)} viajes del CSV (separador: '{separator}')")

    # Initialize database
    init_db()
    print("[OK] Base de datos inicializada")

    # Import trips
    imported = 0
    skipped = 0
    categories = {'Laburo': 0, 'Personal': 0, '': 0}

    for row in trips:
        date_normalized = normalize_date(row.get('date', ''))
        category = row.get('Category', '').strip()

        # Handle 'nan' or empty
        if category == 'nan':
            category = ''

        trip_data = {
            'filename': row.get('filename', ''),
            'service': row.get('service', ''),
            'date': date_normalized,
            'origin': row.get('origin', ''),
            'destination': row.get('destination', ''),
            'amount': float(row.get('amount', 0)),
            'currency': row.get('currency', 'ARS'),
            'category': category,
        }

        upsert_trip_with_category(trip_data)
        imported += 1
        categories[category] = categories.get(category, 0) + 1

    # Verify
    all_trips = get_all_trips()
    laburo = [t for t in all_trips if t['category'] == 'Laburo']
    personal = [t for t in all_trips if t['category'] == 'Personal']

    print(f"\n{'='*60}")
    print(f"MIGRACION COMPLETADA")
    print(f"{'='*60}")
    print(f"[OK] Viajes importados: {imported}")
    print(f"[OK] Total en base de datos: {len(all_trips)}")
    print(f"     - Laburo: {len(laburo)} viajes")
    print(f"     - Personal: {len(personal)} viajes")
    print(f"     - Sin categoria: {len(all_trips) - len(laburo) - len(personal)} viajes")
    print(f"\n[OK] Base de datos: data/expense_tracker.db")
    print(f"{'='*60}")

    return True


if __name__ == '__main__':
    migrate()
