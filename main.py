#!/usr/bin/env python3
"""
Uber/Didi Expense Analyzer - Main Script

Usage:
    python main.py                  # Parse receipts and generate CSV
    python main.py --summary         # Generate summary report from categorized CSV
    python main.py --db              # Parse receipts and store in SQLite database
    python main.py --summary --db    # Generate summary from database
    python main.py --download        # Download new receipts from Gmail (requires setup)
    python main.py --pipeline        # Run full automated pipeline
    python main.py --web             # Launch web interface
"""
import argparse
from pathlib import Path
import pandas as pd
from parser import parse_receipt
from datetime import datetime


def parse_all_receipts(receipts_dir='receipts', output_dir='output', use_db=False):
    """
    Parse all receipt files and generate CSV (or store in DB)

    Args:
        receipts_dir: Directory containing .eml/.html files
        output_dir: Directory for output files
        use_db: If True, store results in SQLite instead of CSV
    """
    receipts_dir = Path(receipts_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Find all receipt files
    receipt_files = list(receipts_dir.glob('*.eml')) + list(receipts_dir.glob('*.html'))

    if not receipt_files:
        print(f"No receipt files found in {receipts_dir}/")
        return

    print(f"Found {len(receipt_files)} receipt files\n")

    # Parse each receipt
    trips = []
    failed = []

    for receipt_file in receipt_files:
        try:
            trip_data = parse_receipt(receipt_file)
            if trip_data:
                trips.append(trip_data)
                print(f"[OK] {receipt_file.name}")
            else:
                failed.append(receipt_file.name)
                print(f"[X] {receipt_file.name}: Failed to parse")
        except Exception as e:
            failed.append(receipt_file.name)
            print(f"[X] {receipt_file.name}: {e}")

    if not trips:
        print("\nNo trips were successfully parsed")
        return

    if use_db:
        # Store in SQLite
        from services.database import init_db, upsert_trip

        init_db()
        inserted = 0
        duplicates = 0

        for trip in trips:
            if upsert_trip(trip):
                inserted += 1
            else:
                duplicates += 1

        print(f"\n{'='*60}")
        print(f"[OK] Successfully parsed: {len(trips)} trips")
        print(f"[OK] Inserted in database: {inserted} new trips")
        if duplicates > 0:
            print(f"[!] Duplicates skipped: {duplicates}")
        if failed:
            print(f"[X] Failed: {len(failed)} files")
            for f in failed:
                print(f"    - {f}")
        print(f"{'='*60}")
        return {'parsed': len(trips), 'inserted': inserted, 'duplicates': duplicates}

    else:
        # Original CSV behavior
        df = pd.DataFrame(trips)

        # Detect and remove duplicates
        original_count = len(df)
        df['_dup_key'] = (
            df['date'].astype(str) + '|' +
            df['service'].astype(str) + '|' +
            df['amount'].astype(str) + '|' +
            df['origin'].astype(str) + '|' +
            df['destination'].astype(str)
        )

        df_deduped = df.drop_duplicates(subset=['_dup_key'], keep='first')
        df_deduped = df_deduped.drop(columns=['_dup_key'])

        duplicates_removed = original_count - len(df_deduped)

        if duplicates_removed > 0:
            print(f"\n[!] Found and removed {duplicates_removed} duplicate trips")

        df = df_deduped

        # Add empty Category column for manual filling
        df['Category'] = ''

        # Sort by date
        df = df.sort_values('date', na_position='last')

        # Reorder columns
        columns = ['filename', 'service', 'date', 'origin', 'destination', 'amount', 'currency', 'Category']
        df = df[columns]

        # Save to CSV
        csv_path = output_dir / 'uber_trips.csv'
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')

        # Print summary
        print(f"\n{'='*60}")
        print(f"[OK] Successfully parsed: {len(trips)} trips")
        if failed:
            print(f"[X] Failed: {len(failed)} files")
            for f in failed:
                print(f"    - {f}")

        print(f"\n[OK] Generated: {csv_path}")
        print(f"{'='*60}")
        print("\nNext steps:")
        print("1. Open output/uber_trips.csv in Excel or a text editor")
        print("2. Fill the 'Category' column with 'Personal' or 'Laburo'")
        print("3. Save the file")
        print("4. Run: python main.py --summary")


def generate_summary(csv_path='output/uber_trips.csv', output_dir='output', use_db=False):
    """
    Generate markdown summary from categorized CSV or database.

    Args:
        csv_path: Path to CSV with categorized trips
        output_dir: Directory for output files
        use_db: If True, read from SQLite instead of CSV
    """
    output_dir = Path(output_dir)

    if use_db:
        from services.database import get_summary_stats, get_all_trips

        stats = get_summary_stats()

        if stats['total_trips'] == 0:
            print("No trips in database. Run: python main.py --db")
            return

        if not stats['by_category']:
            print("Warning: No trips have been categorized yet")
            return

        # Generate markdown
        md_lines = []
        md_lines.append("# Uber/Didi Expense Summary")
        md_lines.append(f"\n**Report generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        md_lines.append(f"\n**Total trips analyzed:** {stats['total_trips']}")

        md_lines.append("\n## Overall Totals by Category\n")
        for category, data in stats['by_category'].items():
            md_lines.append(f"- **{category}**: ARS {data['total']:,.2f} ({data['count']} trips)")

        md_lines.append("\n## By Service\n")
        for service, data in stats['by_service'].items():
            md_lines.append(f"- **{service}**: ARS {data['total']:,.2f} ({data['count']} trips)")

        md_lines.append("\n## Monthly Breakdown\n")
        for month in sorted(stats['by_month'].keys(), reverse=True):
            md_lines.append(f"### {month}")
            month_total = 0
            month_count = 0
            for category, data in stats['by_month'][month].items():
                md_lines.append(f"- **{category}**: ARS {data['total']:,.2f} ({data['count']} trips)")
                month_total += data['total']
                month_count += data['count']
            md_lines.append(f"- *Month Total*: ARS {month_total:,.2f} ({month_count} trips)")
            md_lines.append("")

        if stats['uncategorized_count'] > 0:
            md_lines.append(f"\n---\n[!]  **{stats['uncategorized_count']} trips are not categorized yet**")

        md_path = output_dir / 'summary.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        # Print to console
        print("\n" + "="*60)
        print("EXPENSE SUMMARY (from database)")
        print("="*60)
        for category, data in stats['by_category'].items():
            print(f"{category}: ARS {data['total']:,.2f} ({data['count']} trips)")
        print("="*60)
        print(f"\n[OK] Generated: {md_path}")
        if stats['uncategorized_count'] > 0:
            print(f"[!]  {stats['uncategorized_count']} trips still need categorization")

    else:
        # Original CSV behavior
        csv_path = Path(csv_path)

        if not csv_path.exists():
            print(f"Error: {csv_path} not found")
            print("Run without --summary first to generate the CSV")
            return

        # Read CSV - auto-detect separator
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            separator = ';' if ';' in first_line else ','

        df = pd.read_csv(csv_path, sep=separator, encoding='utf-8-sig')

        if df['Category'].isna().all() or (df['Category'] == '').all():
            print("Warning: No trips have been categorized yet")
            print("Please fill the 'Category' column in the CSV first")
            return

        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['month'] = df['date'].dt.to_period('M')

        categorized = df[df['Category'].notna() & (df['Category'] != '')]

        if len(categorized) == 0:
            print("No categorized trips found")
            return

        total_trips = len(categorized)

        by_category = categorized.groupby('Category').agg({
            'amount': 'sum',
            'filename': 'count'
        }).rename(columns={'filename': 'count'})

        by_month_category = categorized.groupby(['month', 'Category']).agg({
            'amount': 'sum',
            'filename': 'count'
        }).rename(columns={'filename': 'count'})

        by_service = categorized.groupby('service').agg({
            'amount': 'sum',
            'filename': 'count'
        }).rename(columns={'filename': 'count'})

        md_lines = []
        md_lines.append("# Uber/Didi Expense Summary")
        md_lines.append(f"\n**Report generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        md_lines.append(f"\n**Total trips analyzed:** {total_trips}")

        md_lines.append("\n## Overall Totals by Category\n")
        for category, row in by_category.iterrows():
            md_lines.append(f"- **{category}**: ARS {row['amount']:,.2f} ({int(row['count'])} trips)")

        md_lines.append("\n## By Service\n")
        for service, row in by_service.iterrows():
            md_lines.append(f"- **{service}**: ARS {row['amount']:,.2f} ({int(row['count'])} trips)")

        md_lines.append("\n## Monthly Breakdown\n")

        months = sorted(by_month_category.index.get_level_values(0).unique(), reverse=True)

        for month in months:
            md_lines.append(f"### {month}")
            month_data = by_month_category.loc[month]

            if isinstance(month_data, pd.Series):
                category = month_data.name
                md_lines.append(f"- **{category}**: ARS {month_data['amount']:,.2f} ({int(month_data['count'])} trips)")
            else:
                for category, row in month_data.iterrows():
                    md_lines.append(f"- **{category}**: ARS {row['amount']:,.2f} ({int(row['count'])} trips)")

            month_total = month_data['amount'].sum() if isinstance(month_data, pd.DataFrame) else month_data['amount']
            month_count = month_data['count'].sum() if isinstance(month_data, pd.DataFrame) else month_data['count']
            md_lines.append(f"- *Month Total*: ARS {month_total:,.2f} ({int(month_count)} trips)")
            md_lines.append("")

        uncategorized = df[(df['Category'].isna()) | (df['Category'] == '')]
        if len(uncategorized) > 0:
            md_lines.append(f"\n---\n[!]  **{len(uncategorized)} trips are not categorized yet**")

        md_path = output_dir / 'summary.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        print("\n" + "="*60)
        print("EXPENSE SUMMARY")
        print("="*60)
        for category, row in by_category.iterrows():
            print(f"{category}: ARS {row['amount']:,.2f} ({int(row['count'])} trips)")

        print("\n" + "-"*60)
        for month in months:
            month_data = by_month_category.loc[month]
            month_total = month_data['amount'].sum() if isinstance(month_data, pd.DataFrame) else month_data['amount']
            print(f"{month}: ARS {month_total:,.2f}")

        print("="*60)
        print(f"\n[OK] Generated: {md_path}")
        if len(uncategorized) > 0:
            print(f"[!]  {len(uncategorized)} trips still need categorization")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Uber/Didi Expense Analyzer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                  # Parse receipts and generate CSV
  python main.py --summary        # Generate summary from categorized CSV
  python main.py --db             # Parse and store in SQLite database
  python main.py --summary --db   # Summary from database
  python main.py --download       # Download receipts from Gmail
  python main.py --pipeline       # Run full automated pipeline
  python main.py --web            # Launch web interface
        """
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Generate summary report from categorized CSV'
    )
    parser.add_argument(
        '--db',
        action='store_true',
        help='Use SQLite database instead of CSV'
    )
    parser.add_argument(
        '--download',
        action='store_true',
        help='Download new receipts from Gmail (requires credentials.json)'
    )
    parser.add_argument(
        '--pipeline',
        action='store_true',
        help='Run full automated pipeline (download + parse + categorize + PDF)'
    )
    parser.add_argument(
        '--web',
        action='store_true',
        help='Launch web interface on localhost:5000'
    )

    args = parser.parse_args()

    if args.web:
        from run_web import launch
        launch()
    elif args.pipeline:
        from services.pipeline import run_full_pipeline
        run_full_pipeline(download_gmail=args.download)
    elif args.download:
        from services.gmail_service import download_new_receipts
        download_new_receipts()
    elif args.summary:
        generate_summary(use_db=args.db)
    else:
        parse_all_receipts(use_db=args.db)


if __name__ == '__main__':
    main()
