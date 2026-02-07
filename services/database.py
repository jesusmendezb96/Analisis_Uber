#!/usr/bin/env python3
"""
SQLite database service for Uber/Didi Expense Tracker.
Replaces CSV as the source of truth with proper deduplication and querying.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / 'data' / 'expense_tracker.db'


def get_db_path():
    """Return the database file path, ensuring parent directory exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return str(DB_PATH)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database schema. Safe to call multiple times."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                service TEXT NOT NULL,
                date TEXT NOT NULL,
                origin TEXT,
                destination TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'ARS',
                category TEXT DEFAULT '',
                auto_categorized INTEGER DEFAULT 0,
                needs_review INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(date, service, amount, origin, destination)
            );

            CREATE TABLE IF NOT EXISTS downloaded_emails (
                message_id TEXT PRIMARY KEY,
                subject TEXT,
                sender TEXT,
                filename TEXT,
                downloaded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT DEFAULT (datetime('now')),
                finished_at TEXT,
                status TEXT DEFAULT 'running',
                emails_downloaded INTEGER DEFAULT 0,
                trips_parsed INTEGER DEFAULT 0,
                duplicates_skipped INTEGER DEFAULT 0,
                trips_categorized INTEGER DEFAULT 0,
                pdfs_generated INTEGER DEFAULT 0,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_trips_date ON trips(date);
            CREATE INDEX IF NOT EXISTS idx_trips_category ON trips(category);
            CREATE INDEX IF NOT EXISTS idx_trips_service ON trips(service);
        """)


def upsert_trip(trip_data):
    """
    Insert a trip, ignoring duplicates (same date+service+amount+origin+destination).

    Args:
        trip_data: dict with keys: filename, service, date, origin, destination, amount, currency

    Returns:
        True if inserted, False if duplicate
    """
    with get_connection() as conn:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO trips
                    (filename, service, date, origin, destination, amount, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trip_data['filename'],
                trip_data['service'],
                trip_data['date'],
                trip_data.get('origin', ''),
                trip_data.get('destination', ''),
                trip_data['amount'],
                trip_data.get('currency', 'ARS'),
            ))
            return conn.total_changes > 0
        except sqlite3.IntegrityError:
            return False


def upsert_trip_with_category(trip_data):
    """
    Insert a trip with an existing category (for migration).
    Ignores duplicates.

    Args:
        trip_data: dict with keys including 'category'
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO trips
                (filename, service, date, origin, destination, amount, currency, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_data['filename'],
            trip_data['service'],
            trip_data['date'],
            trip_data.get('origin', ''),
            trip_data.get('destination', ''),
            trip_data['amount'],
            trip_data.get('currency', 'ARS'),
            trip_data.get('category', ''),
        ))


def get_all_trips(category_filter=None, month_filter=None, needs_review=None):
    """
    Get all trips, optionally filtered.

    Args:
        category_filter: 'Laburo', 'Personal', or '' for uncategorized
        month_filter: 'YYYY-MM' string
        needs_review: True to show only trips needing review

    Returns:
        List of dict-like Row objects
    """
    with get_connection() as conn:
        query = "SELECT * FROM trips WHERE 1=1"
        params = []

        if category_filter is not None:
            query += " AND category = ?"
            params.append(category_filter)

        if month_filter:
            # Match trips where date contains this year-month
            # Dates stored as YYYY-MM-DD
            query += " AND substr(date, 1, 7) = ?"
            params.append(month_filter)

        if needs_review:
            query += " AND needs_review = 1"

        query += " ORDER BY date ASC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_trip_by_id(trip_id):
    """Get a single trip by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        return dict(row) if row else None


def update_trip_category(trip_id, category):
    """Update the category of a trip."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE trips SET category = ?, needs_review = 0, updated_at = datetime('now')
            WHERE id = ?
        """, (category, trip_id))


def bulk_update_categories(updates):
    """
    Bulk update categories.

    Args:
        updates: list of (trip_id, category) tuples
    """
    with get_connection() as conn:
        conn.executemany("""
            UPDATE trips SET category = ?, auto_categorized = 1, updated_at = datetime('now')
            WHERE id = ?
        """, [(cat, tid) for tid, cat in updates])


def get_summary_stats():
    """
    Get summary statistics for the dashboard.

    Returns:
        dict with total_trips, by_category, by_month, by_service, uncategorized_count
    """
    with get_connection() as conn:
        # Total trips
        total = conn.execute("SELECT COUNT(*) as cnt FROM trips").fetchone()['cnt']

        # By category
        by_category = {}
        rows = conn.execute("""
            SELECT category, COUNT(*) as cnt, SUM(amount) as total
            FROM trips WHERE category != '' GROUP BY category
        """).fetchall()
        for row in rows:
            by_category[row['category']] = {
                'count': row['cnt'],
                'total': row['total'] or 0
            }

        # By month
        by_month = {}
        rows = conn.execute("""
            SELECT substr(date, 1, 7) as month, category,
                   COUNT(*) as cnt, SUM(amount) as total
            FROM trips WHERE category != ''
            GROUP BY month, category ORDER BY month
        """).fetchall()
        for row in rows:
            month = row['month']
            if month not in by_month:
                by_month[month] = {}
            by_month[month][row['category']] = {
                'count': row['cnt'],
                'total': row['total'] or 0
            }

        # By service
        by_service = {}
        rows = conn.execute("""
            SELECT service, COUNT(*) as cnt, SUM(amount) as total
            FROM trips GROUP BY service
        """).fetchall()
        for row in rows:
            by_service[row['service']] = {
                'count': row['cnt'],
                'total': row['total'] or 0
            }

        # Uncategorized count
        uncategorized = conn.execute(
            "SELECT COUNT(*) as cnt FROM trips WHERE category = '' OR category IS NULL"
        ).fetchone()['cnt']

        # Needs review count
        needs_review = conn.execute(
            "SELECT COUNT(*) as cnt FROM trips WHERE needs_review = 1"
        ).fetchone()['cnt']

        return {
            'total_trips': total,
            'by_category': by_category,
            'by_month': by_month,
            'by_service': by_service,
            'uncategorized_count': uncategorized,
            'needs_review_count': needs_review,
        }


def get_available_months():
    """Get list of months that have trips, for filter dropdowns."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT substr(date, 1, 7) as month
            FROM trips ORDER BY month DESC
        """).fetchall()
        return [row['month'] for row in rows]


def export_to_csv(output_path, category_filter=None):
    """
    Export trips to CSV (backward compatible with original format).

    Args:
        output_path: Path for output CSV file
        category_filter: Optional category to filter by
    """
    import csv

    trips = get_all_trips(category_filter=category_filter)

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['filename', 'service', 'date', 'origin', 'destination',
                         'amount', 'currency', 'Category'])
        for trip in trips:
            writer.writerow([
                trip['filename'], trip['service'], trip['date'],
                trip['origin'], trip['destination'], trip['amount'],
                trip['currency'], trip['category']
            ])


def record_downloaded_email(message_id, subject, sender, filename):
    """Record a downloaded email to avoid re-downloading."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO downloaded_emails (message_id, subject, sender, filename)
            VALUES (?, ?, ?, ?)
        """, (message_id, subject, sender, filename))


def is_email_downloaded(message_id):
    """Check if an email has already been downloaded."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM downloaded_emails WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None


def get_downloaded_emails():
    """Get list of all downloaded emails."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM downloaded_emails ORDER BY downloaded_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def start_pipeline_run():
    """Record start of a pipeline run. Returns run ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO pipeline_runs (status) VALUES ('running')"
        )
        return cursor.lastrowid


def finish_pipeline_run(run_id, stats, error=None):
    """Record completion of a pipeline run."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE pipeline_runs SET
                finished_at = datetime('now'),
                status = ?,
                emails_downloaded = ?,
                trips_parsed = ?,
                duplicates_skipped = ?,
                trips_categorized = ?,
                pdfs_generated = ?,
                error_message = ?
            WHERE id = ?
        """, (
            'error' if error else 'completed',
            stats.get('emails_downloaded', 0),
            stats.get('trips_parsed', 0),
            stats.get('duplicates_skipped', 0),
            stats.get('trips_categorized', 0),
            stats.get('pdfs_generated', 0),
            error,
            run_id,
        ))


def get_pipeline_runs(limit=10):
    """Get recent pipeline runs."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
