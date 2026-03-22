#!/usr/bin/env python3
"""Entry point for the Uber/Didi Expense Analyzer web interface."""
import webbrowser
import threading


def _check_gmail_token():
    """Warn on startup if Gmail token is expired. Does not block launch."""
    try:
        from services.gmail_service import is_configured, validate_credentials
        if not is_configured():
            return
        valid, _ = validate_credentials()
        if not valid:
            print("\n[!] Token de Gmail expirado.")
            print("    Abre /gmail en la UI y haz clic en 'Re-autenticar Gmail'.")
    except Exception:
        pass  # Never block startup due to token check failures


def launch():
    """Launch the Flask web app and open browser."""
    _check_gmail_token()

    from web import create_app
    app = create_app()

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open('http://localhost:5000')

    threading.Thread(target=open_browser, daemon=True).start()

    print("\n" + "="*60)
    print("Uber/Didi Expense Analyzer - Web Interface")
    print("="*60)
    print("Abriendo en: http://localhost:5000")
    print("Presiona Ctrl+C para detener el servidor")
    print("="*60 + "\n")

    app.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == '__main__':
    launch()
