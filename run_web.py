#!/usr/bin/env python3
"""Entry point for the Uber/Didi Expense Analyzer web interface."""
import webbrowser
import threading


def launch():
    """Launch the Flask web app and open browser."""
    from web import create_app
    app = create_app()

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open('http://localhost:5100')

    threading.Thread(target=open_browser, daemon=True).start()

    print("\n" + "="*60)
    print("Uber/Didi Expense Analyzer - Web Interface")
    print("="*60)
    print("Abriendo en: http://localhost:5100")
    print("Presiona Ctrl+C para detener el servidor")
    print("="*60 + "\n")

    app.run(host='127.0.0.1', port=5100, debug=False)


if __name__ == '__main__':
    launch()
