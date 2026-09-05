# Vercel serverless entrypoint. The Python runtime picks up the ASGI
# `app` object exported here; the real application lives in app.main so
# the Docker/ECS path and the serverless path share one codebase.
from app.main import app

__all__ = ["app"]
