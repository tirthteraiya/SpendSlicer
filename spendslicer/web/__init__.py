"""Web UI — FastAPI backend serving a prebuilt React single-page app.

Run with:
    spendslicer  # starts the dashboard and opens the default browser

Or via the helpers:
    from spendslicer.web.app import serve
    serve(port=8080)
"""

from .app import app, main, serve

__all__ = ["app", "main", "serve"]
