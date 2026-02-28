"""Gmail route - download receipts from Gmail."""
from flask import Blueprint, render_template, request
from services.database import get_downloaded_emails, log_activity
from services import task_runner

_logged_tasks = set()  # Avoid duplicate logs from htmx polling

bp = Blueprint('gmail', __name__, url_prefix='/gmail')


@bp.route('/')
def index():
    """Gmail download page."""
    from services.gmail_service import is_configured

    downloaded = get_downloaded_emails()
    configured = is_configured()

    return render_template('gmail.html',
        configured=configured,
        downloaded_emails=downloaded,
        total_downloaded=len(downloaded),
    )


@bp.route('/download', methods=['POST'])
def download():
    """Start Gmail download (runs in background)."""
    from services.gmail_service import is_configured, validate_credentials, download_new_receipts

    if not is_configured():
        return render_template('_alert.html',
            message='Gmail no configurado. Coloca credentials.json en config/',
            type='danger'
        )

    # Pre-flight: validate credentials synchronously before dispatching to background.
    # Catches expired/revoked tokens with an actionable error message.
    valid, error = validate_credentials()
    if not valid:
        return render_template('_alert.html', message=error, type='danger')

    after_date = request.form.get('after_date') or None

    tid = task_runner.submit(
        download_new_receipts,
        after_date=after_date,
        description="Descargando emails de Gmail"
    )

    return render_template('_task_status.html', task_id=tid, description="Descargando emails...",
                           status_url=f"/gmail/task-status/{tid}")


@bp.route('/task-status/<task_id>')
def task_status(task_id):
    """Poll task status (htmx polling endpoint)."""
    status = task_runner.get_status(task_id)
    if not status:
        return '<div class="alert alert-warning">Tarea no encontrada</div>'

    if status['status'] == 'completed':
        if task_id not in _logged_tasks:
            _logged_tasks.add(task_id)
            result = status.get('result', {})
            count = result.get('downloaded', 0) if isinstance(result, dict) else 0
            log_activity('gmail_download', f'{count} emails descargados desde Gmail')

        return render_template('_alert.html',
            message='Descarga completada. Recarga la pagina para ver los resultados.',
            type='success'
        )
    elif status['status'] == 'error':
        if task_id not in _logged_tasks:
            _logged_tasks.add(task_id)
            log_activity('gmail_download', f'Error en descarga: {status["error"]}', status='error')

        return render_template('_alert.html',
            message=f'Error: {status["error"]}',
            type='danger'
        )
    else:
        return render_template('_task_status.html',
            task_id=task_id,
            description=f"Descargando... {status.get('progress', 0)}%",
            status_url=f"/gmail/task-status/{task_id}"
        )
