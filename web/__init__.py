#!/usr/bin/env python3
"""Flask application factory for Uber/Didi Expense Analyzer web UI."""
from flask import Flask
from pathlib import Path
import sys

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / 'templates'),
        static_folder=str(Path(__file__).parent / 'static'),
    )
    app.secret_key = 'uber-didi-expense-tracker-local-only'

    # Initialize database
    from services.database import init_db
    init_db()

    # Register blueprints
    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.trips import bp as trips_bp
    from web.routes.gmail import bp as gmail_bp
    from web.routes.reports import bp as reports_bp
    from web.routes.settings import bp as settings_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(gmail_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    return app
