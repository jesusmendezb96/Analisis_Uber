#!/usr/bin/env python3
"""
Auto-categorize trips based on known addresses.
This is a backward-compatible wrapper around services/categorizer.py.

Can operate in two modes:
- CSV mode (default): reads/writes output/uber_trips.csv directly
- DB mode: uses services/categorizer.categorize_all_trips()
"""
import sys
from pathlib import Path

# Check if running in DB mode
if '--db' in sys.argv:
    from services.database import init_db
    from services.categorizer import categorize_all_trips

    init_db()
    stats = categorize_all_trips()

    print(f"\n{'='*60}")
    print(f"AUTO-CATEGORIZATION COMPLETE (database mode)")
    print(f"{'='*60}")
    print(f"[OK] Automatically categorized: {stats['categorized']} trips")
    print(f"     - Laburo: {stats['work']}")
    print(f"     - Personal: {stats['personal']}")
    if stats['needs_review'] > 0:
        print(f"[!] Needs manual review: {stats['needs_review']} trips")
    print(f"{'='*60}")

else:
    # Original CSV mode
    import pandas as pd
    from services.categorizer import normalize_address, categorize_trip

    csv_path = Path('output/uber_trips.csv')

    # Auto-detect separator
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        first_line = f.readline()
        separator = ';' if ';' in first_line else ','

    df = pd.read_csv(csv_path, sep=separator, encoding='utf-8-sig')

    # Ensure Category column is string type
    df['Category'] = df['Category'].astype(str).replace('nan', '')

    # Auto-categorize
    categorized = 0
    manual_review = 0

    for idx, row in df.iterrows():
        category = categorize_trip(row['origin'], row['destination'])
        if category:
            df.at[idx, 'Category'] = category
            categorized += 1
        else:
            if pd.isna(row['Category']) or row['Category'] == '' or row['Category'] == 'nan':
                df.at[idx, 'Category'] = ''
                manual_review += 1

    # Save
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    print(f"\n{'='*60}")
    print(f"AUTO-CATEGORIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"[OK] Automatically categorized: {categorized} trips")
    if manual_review > 0:
        print(f"[!] Needs manual review: {manual_review} trips")
    print(f"\nCategories assigned:")
    print(df['Category'].value_counts().to_string())
    print(f"\n{'='*60}")
