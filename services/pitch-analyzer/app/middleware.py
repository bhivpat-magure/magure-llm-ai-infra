# app/middleware/jwt_middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request, HTTPException
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')

EXCLUDE_PATHS = ["/docs", "/openapi.json", "/redoc"]

class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ✅ Skip OPTIONS preflight
        if request.method == "OPTIONS":
            return Response(status_code=200)

        # ✅ Skip excluded paths
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
