"""Dashboard route - main page with stats and quick actions."""
from flask import Blueprint, render_template
from services.database import get_summary_stats, get_available_months, get_pipeline_runs, get_activity_log

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    """Main dashboard with summary statistics."""
    stats = get_summary_stats()
    months = get_available_months()
    recent_runs = get_pipeline_runs(limit=5)
    activity_log = get_activity_log(limit=15)

    # Calculate totals for display
    total_laburo = stats['by_category'].get('Laburo', {}).get('total', 0)
    total_personal = stats['by_category'].get('Personal', {}).get('total', 0)
    total_all = total_laburo + total_personal

    return render_template('dashboard.html',
        stats=stats,
        months=months,
        recent_runs=recent_runs,
        activity_log=activity_log,
        total_laburo=total_laburo,
        total_personal=total_personal,
        total_all=total_all,
    )
