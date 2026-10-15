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

from apps.api.src.main import app

# Export ASGI application for Vercel
__all__ = ["app"]
