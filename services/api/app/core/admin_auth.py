import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import get_settings

_security = HTTPBasic()


def require_admin_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
    """FastAPI dependency gating every /admin route. Fails closed: if
    admin_basic_auth_user/password aren't configured, every request is
    rejected rather than silently left open. Uses compare_digest for both
    fields to avoid leaking credential length/prefix via timing."""
    settings = get_settings()
    valid_user = settings.admin_basic_auth_user
    valid_password = settings.admin_basic_auth_password

    user_ok = bool(valid_user) and secrets.compare_digest(credentials.username, valid_user)
    password_ok = bool(valid_password) and secrets.compare_digest(credentials.password, valid_password)

    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
