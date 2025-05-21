import asyncio

import jwt
from datetime import datetime, timedelta
from crud.user import get_user, apply_api_key
from fastapi import HTTPException, Depends, Request, status
import os
from database.models import User, RoleEnum

class OAuth2TokenWithPrefix:
    def __init__(self, token_prefix: str = "TOKEN"):
        self.token_prefix = token_prefix

    async def __call__(self, request: Request) -> str:
        authorization: str = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing",
                headers={"WWW-Authenticate": self.token_prefix},
            )
        try:
            prefix, token = authorization.split(" ")
            if prefix != self.token_prefix:
                raise ValueError("Invalid token prefix")
            return token
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format",
                headers={"WWW-Authenticate": self.token_prefix},
            )

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM")
oauth2_scheme = OAuth2TokenWithPrefix(token_prefix="TOKEN")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    asyncio.get_running_loop().create_task(apply_api_key(data['id'], encoded_jwt))
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "TOKEN"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_: str = payload.get("id")
        if id_ is None:
            raise credentials_exception
    except jwt.exceptions.PyJWTError as e:
        raise credentials_exception

    user = await get_user(id_)
    if user:
        return user
    raise credentials_exception

async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != RoleEnum.ADMIN:
        raise HTTPException(
                status_code=403,
                detail="Permission denied",
                headers={"WWW-Authenticate": "TOKEN"},
                )
    return user

