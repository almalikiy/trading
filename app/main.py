"""Legacy app entrypoint kept as a thin compatibility adapter.

The canonical runtime API now lives under trading_bot.app.main. This module
re-exports the canonical FastAPI app so the refactored backend remains the
single source of truth while older startup scripts and compatibility callers
can continue to resolve the app from app.main.
"""

from trading_bot.app.main import app as canonical_app

# Legacy entrypoints should resolve to the canonical implementation instead of
# carrying their own startup logic or duplicate business endpoints.
app = canonical_app

__all__ = ["app"]
