"""Web UI — FastAPI backend serving a prebuilt React single-page app.

Run with:
    spendslicer-web  # open the protected link printed in the terminal

Or via the helpers:
    from spendslicer.web.app import serve
    serve(port=8080)
"""

from .app import app, main, serve

__all__ = ["app", "main", "serve"]
