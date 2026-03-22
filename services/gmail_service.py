#!/usr/bin/env python3
"""
Gmail API service for downloading Uber/Didi receipt emails.
Uses OAuth2 for authentication (opens browser first time, then auto-refresh).
"""
import base64
import email as email_lib
import json
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path(__file__).parent.parent / 'config'
CREDENTIALS_PATH = CONFIG_DIR / 'credentials.json'
TOKEN_PATH = CONFIG_DIR / 'token.json'
RECEIPTS_DIR = Path(__file__).parent.parent / 'receipts'

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

_REAUTH_MSG = (
    "Token de Gmail expirado o revocado. Para re-autenticar, ejecuta desde CLI:\n"
    '  python -c "from services.gmail_service import get_gmail_service; get_gmail_service()"'
)


def _load_gmail_config():
    """Load Gmail search query from settings."""
    settings_path = CONFIG_DIR / 'settings.json'
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            return settings.get('gmail', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def is_configured():
    """Check if Gmail API credentials are set up."""
    return CREDENTIALS_PATH.exists()


def validate_credentials():
    """
    Validate existing credentials WITHOUT triggering OAuth browser flow.
    Use this for pre-flight checks from the web UI.

    Returns:
        (is_valid: bool, error_message: str or None)
    """
    if not CREDENTIALS_PATH.exists():
        return False, "credentials.json no encontrado en config/"

    if not TOKEN_PATH.exists():
        return False, (
            "No hay token guardado. Ejecuta la autenticación inicial desde CLI:\n"
            '  python -c "from services.gmail_service import get_gmail_service; get_gmail_service()"'
        )

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import google.auth.exceptions

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except Exception as e:
        return False, f"Token inválido o corrupto: {e}. Borra config/token.json y re-autentica."

    if creds.valid:
        return True, None

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w') as f:
                f.write(creds.to_json())
            return True, None
        except google.auth.exceptions.RefreshError:
            return False, _REAUTH_MSG
        except Exception as e:
            return False, f"Error al refrescar token: {e}"

    return False, _REAUTH_MSG


def get_gmail_service():
    """
    Get authenticated Gmail API service.
    Opens browser for OAuth consent on first use, then auto-refreshes.

    Returns:
        Gmail API service object

    Raises:
        FileNotFoundError: if credentials.json is missing
        Exception: on auth failure
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "credentials.json no encontrado en config/.\n"
            "Sigue las instrucciones en SETUP_GMAIL.md para configurar Gmail API."
        )

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import google.auth.exceptions

    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except google.auth.exceptions.RefreshError:
                # Token revocado — necesita re-autenticación completa
                print(f"[!] {_REAUTH_MSG}")
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next time
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def search_receipts(after_date=None):
    """
    Search Gmail for Uber/Didi receipt emails.

    Args:
        after_date: Only get emails after this date (YYYY-MM-DD string)

    Returns:
        List of message dicts with 'id' and 'threadId'
    """
    service = get_gmail_service()

    gmail_config = _load_gmail_config()
    query = gmail_config.get(
        'search_query',
        'subject:"Tu viaje" (from:noreply@uber.com OR from:didi@ar.didiglobal.com)'
    )

    if after_date:
        query += f" after:{after_date}"

    messages = []
    page_token = None

    while True:
        results = service.users().messages().list(
            userId='me', q=query, pageToken=page_token
        ).execute()

        if 'messages' in results:
            messages.extend(results['messages'])

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return messages


def download_email(message_id, service=None):
    """
    Download a single email as .eml file.

    Args:
        message_id: Gmail message ID
        service: Gmail API service (optional, will create if not provided)

    Returns:
        tuple (filename, subject, sender) or None on failure
    """
    if service is None:
        service = get_gmail_service()

    # Single API call: raw format contains headers + body
    msg = service.users().messages().get(
        userId='me', id=message_id, format='raw'
    ).execute()

    raw_data = msg.get('raw', '')
    email_bytes = base64.urlsafe_b64decode(raw_data)

    # Extract headers from raw email (no second API call needed)
    parsed_msg = email_lib.message_from_bytes(email_bytes)
    subject = parsed_msg.get('Subject', 'Unknown')
    sender = parsed_msg.get('From', '')

    # Filter out promos that slip through the Gmail query
    # Real receipts: "Tu viaje del...", "Tu viaje Uber del...", "Tu viaje Pone Tu Precio del...", "Tu viaje Express del..."
    # Promos: "Tu viaje de la manana cuesta menos", etc.
    _promo_keywords = ['cuesta menos', 'OFF', 'descuento', 'promo', 'gratis', 'regalo']
    if any(kw.lower() in subject.lower() for kw in _promo_keywords):
        return None  # Skip promo emails

    # Generate safe filename from subject
    safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_', '(', ')')).strip()
    if not safe_subject:
        safe_subject = f"email_{message_id[:8]}"

    filename = f"{safe_subject}.eml"

    # Handle duplicate filenames
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RECEIPTS_DIR / filename
    counter = 1
    while filepath.exists():
        filepath = RECEIPTS_DIR / f"{safe_subject} ({counter}).eml"
        counter += 1
    filename = filepath.name

    # Save .eml file
    with open(filepath, 'wb') as f:
        f.write(email_bytes)

    return filename, subject, sender


def download_new_receipts(after_date=None, task_id=None):
    """
    Download all new receipt emails from Gmail (skipping already downloaded ones).

    Args:
        after_date: Only download emails after this date (YYYY-MM-DD)
        task_id: Optional task_id for progress reporting

    Returns:
        dict with downloaded, skipped, errors counts
    """
    from services.database import (
        init_db, is_email_downloaded, record_downloaded_email
    )

    init_db()

    print("[*] Conectando a Gmail...")
    service = get_gmail_service()

    print("[*] Buscando recibos de Uber/Didi...")
    messages = search_receipts(after_date)
    print(f"[OK] Encontrados {len(messages)} emails")

    stats = {'downloaded': 0, 'skipped': 0, 'errors': 0, 'total': len(messages)}

    for i, msg in enumerate(messages):
        msg_id = msg['id']

        # Skip already downloaded
        if is_email_downloaded(msg_id):
            stats['skipped'] += 1
            continue

        try:
            result = download_email(msg_id, service)
            if result:
                filename, subject, sender = result
                record_downloaded_email(msg_id, subject, sender, filename)
                stats['downloaded'] += 1
                print(f"  [OK] {filename}")
            else:
                stats['skipped'] += 1  # Promo filtered out
        except Exception as e:
            stats['errors'] += 1
            print(f"  [X] Error descargando {msg_id}: {e}")

        # Report progress
        if task_id:
            from services import task_runner
            progress = int((i + 1) / len(messages) * 100)
            task_runner.update_progress(task_id, progress, f"{i+1}/{len(messages)}")

    print(f"\n{'='*60}")
    print(f"DESCARGA COMPLETADA")
    print(f"{'='*60}")
    print(f"[OK] Descargados: {stats['downloaded']} nuevos emails")
    print(f"[--] Ya descargados: {stats['skipped']}")
    if stats['errors'] > 0:
        print(f"[X] Errores: {stats['errors']}")
    print(f"{'='*60}")

    return stats
