"""
Vercel Serverless Function Entry Point for CompressPro AI
Enables seamless one-click zero-configuration deployment on Vercel.
"""

import sys
import os

# Ensure project root is available in module search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from apps.api.src.main import app as fastapi_app


async def app(scope, receive, send):
    """
    ASGI entrypoint wrapper for Vercel Serverless Functions.
    Normalizes request paths rewritten by Vercel Edge routing infrastructure.
    """
    if scope["type"] == "http":
        path = scope.get("path", "")

        # 1. Normalize literal function destination path if passed by Vercel rewrite
        if path.startswith("/api/index.py"):
            sub = path[len("/api/index.py"):]
            if not sub:
                sub = "/"
            path = "/api" + sub if not sub.startswith("/api") else sub
            scope["path"] = path
            scope["raw_path"] = path.encode("ascii")

        # 2. Inspect headers for original matched path if rewritten to entrypoint file
        headers = dict(scope.get("headers", []))
        matched = (
            headers.get(b"x-matched-path")
            or headers.get(b"x-forwarded-uri")
            or headers.get(b"x-vercel-matched-path")
            or headers.get(b"x-invoke-path")
        )
        if matched and scope.get("path") in ("/api/index.py", "/api/index", "/api", "/"):
            orig = matched.decode("utf-8", errors="ignore").split("?")[0]
            if orig.startswith("/api/") or orig.startswith("/v1/"):
                scope["path"] = orig
                scope["raw_path"] = orig.encode("ascii")

    await fastapi_app(scope, receive, send)


# Export ASGI application for Vercel
__all__ = ["app"]
