"""Settings route - configure work addresses and view status."""
from flask import Blueprint, render_template, request
from services.categorizer import get_work_addresses, get_home_address, save_settings, _load_settings

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/')
def index():
    """Settings page."""
    from services.gmail_service import is_configured as gmail_configured
    from pathlib import Path

    settings = _load_settings()
    work_addresses = get_work_addresses()
    home_address = get_home_address()
    personal_addresses = settings.get('personal_addresses', [])

    db_path = Path('data/expense_tracker.db')
    db_exists = db_path.exists()
    db_size = f"{db_path.stat().st_size / 1024:.1f} KB" if db_exists else "N/A"

    return render_template('settings.html',
        work_addresses=work_addresses,
        home_address=home_address,
        personal_addresses=personal_addresses,
        gmail_configured=gmail_configured(),
        db_exists=db_exists,
        db_size=db_size,
    )


@bp.route('/save', methods=['POST'])
def save():
    """Save address settings."""
    work_raw = request.form.get('work_addresses', '')
    home = request.form.get('home_address', '').strip().lower()
    personal_raw = request.form.get('personal_addresses', '')

    # Parse textarea (one address per line)
    work = [a.strip().lower() for a in work_raw.strip().split('\n') if a.strip()]
    personal = [a.strip().lower() for a in personal_raw.strip().split('\n') if a.strip()]

    save_settings(work, home, personal)

    return render_template('_alert.html',
        message='Configuracion guardada exitosamente',
        type='success'
    )


@bp.route('/reset', methods=['POST'])
def reset_all():
    """Wipe all data: DB, receipts, output, reintegros. Keeps config."""
    from pathlib import Path
    import shutil
    from services.database import init_db

    deleted = {'eml': 0, 'output': 0, 'reintegros': False}

    # 1. Delete all .eml files
    for f in Path('receipts').glob('*.eml'):
        f.unlink()
        deleted['eml'] += 1

    # 2. Delete database files
    for f in Path('data').glob('expense_tracker.db*'):
        f.unlink()

    # 3. Clean output/
    for f in Path('output').glob('*'):
        f.unlink()
        deleted['output'] += 1

    # 4. Delete reintegros/
    if Path('reintegros').exists():
        shutil.rmtree('reintegros')
        deleted['reintegros'] = True

    # 5. Re-init empty database
    init_db()

    msg = (f"Todo borrado: {deleted['eml']} emails, "
           f"{deleted['output']} archivos output, "
           f"{'carpeta reintegros' if deleted['reintegros'] else 'sin reintegros'}. "
           f"Base de datos reinicializada.")

    return render_template('_alert.html', message=msg, type='warning')
