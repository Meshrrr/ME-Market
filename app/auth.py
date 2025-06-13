from fastapi import Depends, HTTPException, Header
from typing import Optional
from app.models import User, UserRole
from app.database import get_user_by_api_key


async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "token":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    api_key = parts[1]
    user = get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
