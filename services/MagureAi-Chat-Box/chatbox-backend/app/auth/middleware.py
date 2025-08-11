from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from jose import JWTError, jwt
from ..config import settings


EXCLUDED_PATHS = ["/api2/hello","/api2/auth/login", "/api2/auth/register", "/openapi.json", "/docs", "/redoc"]

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(excluded) for excluded in EXCLUDED_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid token"})

        token = auth_header.split(" ")[1]

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            request.state.user_id = payload.get("sub")
            if request.state.user_id is None:
                raise ValueError("Missing user_id in token")
        except JWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        except Exception as e:
            return JSONResponse(status_code=401, content={"detail": str(e)})

        return await call_next(request)