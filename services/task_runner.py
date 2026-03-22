#!/usr/bin/env python3
"""
Background task executor using ThreadPoolExecutor.
Runs PDF generation and Gmail downloads without blocking the web UI.
"""
import inspect
import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

_executor = ThreadPoolExecutor(max_workers=2)
_tasks = {}


def submit(func, *args, description="Task", **kwargs):
    """
    Submit a function to run in the background.

    Automatically injects task_id into kwargs if the function accepts it,
    enabling progress reporting without manual wiring.

    Returns:
        task_id (str)
    """
    cleanup_old_tasks(max_age_hours=1)

    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {
        'status': 'running',
        'description': description,
        'progress': 0,
        'result': None,
        'error': None,
        'started_at': datetime.now().isoformat(),
        'finished_at': None,
    }

    # Auto-inject task_id if the function accepts it
    sig = inspect.signature(func)
    if 'task_id' in sig.parameters and 'task_id' not in kwargs:
        kwargs['task_id'] = task_id

    def wrapper():
        try:
            result = func(*args, **kwargs)
            _tasks[task_id]['status'] = 'completed'
            _tasks[task_id]['result'] = result
        except Exception as e:
            _tasks[task_id]['status'] = 'error'
            _tasks[task_id]['error'] = str(e)
            _tasks[task_id]['result'] = traceback.format_exc()
        finally:
            _tasks[task_id]['finished_at'] = datetime.now().isoformat()

    _executor.submit(wrapper)
    return task_id


def update_progress(task_id, progress, message=None):
    """Update progress for a running task (0-100)."""
    if task_id in _tasks:
        _tasks[task_id]['progress'] = progress
        if message:
            _tasks[task_id]['progress_message'] = message


def get_status(task_id):
    """
    Get status of a task.

    Returns:
        dict with status, progress, result, error, or None if not found
    """
    return _tasks.get(task_id)


def get_all_tasks():
    """Get all tasks (for debug/monitoring)."""
    return dict(_tasks)


def cleanup_old_tasks(max_age_hours=24):
    """Remove completed tasks older than max_age_hours."""
    now = datetime.now()
    to_remove = []
    for task_id, task in _tasks.items():
        if task['finished_at']:
            finished = datetime.fromisoformat(task['finished_at'])
            if (now - finished).total_seconds() > max_age_hours * 3600:
                to_remove.append(task_id)
    for task_id in to_remove:
        del _tasks[task_id]
