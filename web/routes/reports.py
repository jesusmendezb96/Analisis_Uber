"""Reports route - generate summary and PDFs."""
from flask import Blueprint, render_template, send_file
from pathlib import Path
from services.database import get_summary_stats, get_all_trips, log_activity
from services import task_runner

_logged_tasks = set()  # Avoid duplicate logs from htmx polling

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/')
def index():
    """Reports page with generation options."""
    stats = get_summary_stats()

    # Check for existing files
    summary_path = Path('output/summary.md')
    reintegro_dir = Path('reintegros')

    pdf_files = sorted(reintegro_dir.glob('*.pdf')) if reintegro_dir.exists() else []

    return render_template('reports.html',
        stats=stats,
        summary_exists=summary_path.exists(),
        pdf_count=len(pdf_files),
        pdf_files=[f.name for f in pdf_files],
    )


@bp.route('/generate-summary', methods=['POST'])
def generate_summary():
    """Generate summary report."""
    from main import generate_summary as gen_summary
    gen_summary(use_db=True)
    log_activity('generate_summary', 'Reporte summary.md generado')

    return render_template('_alert.html',
        message='Reporte generado: output/summary.md',
        type='success'
    )


@bp.route('/generate-pdfs', methods=['POST'])
def generate_pdfs():
    """Start PDF generation (runs in background)."""
    from flask import request
    from generar_reintegros import generate_reintegros

    force = request.form.get('force_pdfs') == '1'

    tid = task_runner.submit(
        generate_reintegros,
        use_db=True,
        force=force,
        description="Generando PDFs de reintegro"
    )

    return render_template('_task_status.html', task_id=tid, description="Generando PDFs...")


@bp.route('/task-status/<task_id>')
def task_status(task_id):
    """Poll task status (htmx polling endpoint)."""
    status = task_runner.get_status(task_id)
    if not status:
        return '<div class="alert alert-warning">Tarea no encontrada</div>'

    if status['status'] == 'completed':
        result = status.get('result', {})
        if isinstance(result, dict):
            parts = []
            if result.get('emails_downloaded'):
                parts.append(f"{result['emails_downloaded']} emails descargados")
            if result.get('trips_parsed'):
                parts.append(f"{result['trips_parsed']} viajes parseados")
            if result.get('trips_categorized'):
                parts.append(f"{result['trips_categorized']} categorizados")
            if result.get('pdfs_generated'):
                parts.append(f"{result['pdfs_generated']} PDFs generados")
            if result.get('pdfs_skipped'):
                parts.append(f"{result['pdfs_skipped']} PDFs ya existentes")
            message = 'Completado: ' + ', '.join(parts) if parts else 'Completado'
        else:
            message = 'Completado'

        # Log once per task (htmx polls repeatedly)
        if task_id not in _logged_tasks:
            _logged_tasks.add(task_id)
            desc = status.get('description', '')
            if 'PDF' in desc:
                pdfs = result.get('pdfs_generated', 0) if isinstance(result, dict) else 0
                skipped = result.get('pdfs_skipped', 0) if isinstance(result, dict) else 0
                log_activity('generate_pdfs', f'{pdfs} PDFs generados, {skipped} omitidos')
            else:
                log_activity('pipeline', message)

        return render_template('_alert.html',
            message=message,
            type='success'
        )
    elif status['status'] == 'error':
        if task_id not in _logged_tasks:
            _logged_tasks.add(task_id)
            desc = status.get('description', '')
            action = 'generate_pdfs' if 'PDF' in desc else 'pipeline'
            log_activity(action, f'Error: {status["error"]}', status='error')

        return render_template('_alert.html',
            message=f'Error: {status["error"]}',
            type='danger'
        )
    else:
        progress = status.get('progress', 0)
        msg = status.get('progress_message', '')
        return render_template('_task_status.html',
            task_id=task_id,
            description=f"Generando PDFs... {progress}% {msg}"
        )


@bp.route('/run-pipeline', methods=['POST'])
def run_pipeline():
    """Run the full pipeline in background."""
    from services.pipeline import run_full_pipeline
    from flask import request

    include_gmail = request.form.get('include_gmail') == '1'
    after_date = request.form.get('after_date') or None

    tid = task_runner.submit(
        run_full_pipeline,
        download_gmail=include_gmail,
        after_date=after_date,
        description="Pipeline completo"
    )

    return render_template('_task_status.html', task_id=tid, description="Ejecutando pipeline...")
