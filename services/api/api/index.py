# Vercel serverless entrypoint. The Python runtime picks up the ASGI
# `app` object exported here; the real application lives in app.main so
# the Docker/ECS path and the serverless path share one codebase.
from fastapi import APIRouter

from app.main import app

# TEMP DEBUG (remove once DB wiring is verified): scheme/driver only,
# never credentials.
_debug = APIRouter()


@_debug.get("/debug-env")
def debug_env():
    from app.core.config import get_settings

    url = get_settings().database_url
    try:
        import psycopg

        driver = "psycopg3 " + psycopg.__version__
    except Exception as e:
        driver = f"psycopg3 import failed: {e}"
    return {"scheme": url.split("://", 1)[0], "driver": driver}


app.include_router(_debug)

__all__ = ["app"]
