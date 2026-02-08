"""Trips route - list and edit trip categories (htmx inline editing)."""
from flask import Blueprint, render_template, request, jsonify
from services.database import (
    get_all_trips, get_available_months, update_trip_category,
    get_trip_by_id, export_to_csv, get_summary_stats, log_activity
)
from services.categorizer import categorize_all_trips
from pathlib import Path

bp = Blueprint('trips', __name__, url_prefix='/trips')


@bp.route('/')
def list_trips():
    """List all trips with filters."""
    category = request.args.get('category', None)
    month = request.args.get('month', None)
    needs_review = request.args.get('needs_review', None)

    # Normalize empty strings to None
    if category == '':
        category = None
    if month == '':
        month = None

    trips = get_all_trips(
        category_filter=category,
        month_filter=month,
        needs_review=bool(needs_review),
    )
    months = get_available_months()
    stats = get_summary_stats()

    return render_template('trips.html',
        trips=trips,
        months=months,
        stats=stats,
        current_category=category or '',
        current_month=month or '',
        current_needs_review=needs_review,
    )


@bp.route('/<int:trip_id>/category', methods=['POST'])
def update_category(trip_id):
    """Update trip category (htmx endpoint)."""
    category = request.form.get('category', '')
    update_trip_category(trip_id, category)
    log_activity('manual_categorize', f'Viaje #{trip_id} categorizado como {category or "sin categoria"}')

    trip = get_trip_by_id(trip_id)
    if not trip:
        return '<span class="text-danger">Error: viaje no encontrado</span>', 404

    # Return the updated row fragment for htmx swap
    return render_template('_trip_row.html', trip=trip)


@bp.route('/auto-categorize', methods=['POST'])
def auto_categorize():
    """Auto-categorize all uncategorized trips."""
    stats = categorize_all_trips()
    log_activity('auto_categorize',
                 f'{stats["categorized"]} viajes auto-categorizados (Laburo: {stats["work"]}, Personal: {stats["personal"]})')

    # Return htmx redirect to refresh the page
    return '', 200, {'HX-Redirect': '/trips'}


@bp.route('/export-csv', methods=['POST'])
def export_csv():
    """Export trips to CSV file."""
    output_path = Path('output/uber_trips_export.csv')
    output_path.parent.mkdir(exist_ok=True)
    export_to_csv(str(output_path))
    log_activity('export_csv', f'CSV exportado a {output_path}')

    return render_template('_alert.html',
        message=f'CSV exportado: {output_path}',
        type='success'
    )
