from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional
from dotenv import load_dotenv
import secrets
import os

_security = HTTPBasic(auto_error=False)

_DEFAULT_PASSWORDS = {"", "changeme", "admin"}


def _is_first_time_setup() -> bool:
    load_dotenv(override=True)
    pwd = os.getenv("ADMIN_PASSWORD", "")
    return pwd in _DEFAULT_PASSWORDS


def require_admin(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(_security)
):
    load_dotenv(override=True)
    expected_user = os.getenv("ADMIN_USERNAME", "admin")
    expected_pass = os.getenv("ADMIN_PASSWORD", "")

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username.encode(), expected_user.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), expected_pass.encode())

    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True
