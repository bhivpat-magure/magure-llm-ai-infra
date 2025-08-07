# app/middleware/jwt_middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException
from jose import jwt, JWTError

from dotenv import load_dotenv
import os
load_dotenv()


SECRET_KEY=os.getenv('SECRET_KEY')
# Shared with chatbox_backend
JWT_ALGORITHM=os.getenv('JWT_ALGORITHM', 'HS256')
EXCLUDE_PATHS = ["/docs", "/openapi.json", "/redoc"]  # Allow unauthenticated access

class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(path) for path in EXCLUDE_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization header missing or invalid")

        token = auth_header.split(" ")[1]
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return await call_next(request)
