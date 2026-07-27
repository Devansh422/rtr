"""Vercel Python serverless entrypoint.

Vercel's @vercel/python runtime looks for a module-level ASGI callable named
`app` in this file and serves it. The FastAPI application itself lives in
`backend/server.py` and is imported here (never duplicated), so the deployed
API and a locally run `uvicorn backend.server:app` are the exact same app.

The repo root is prepended to sys.path so that `backend` resolves as a package
regardless of the working directory Vercel invokes the function from.
"""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.server import app  # noqa: E402

__all__ = ["app"]
