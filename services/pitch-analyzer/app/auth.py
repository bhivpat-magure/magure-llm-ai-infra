# app/dependencies/auth.py

from fastapi import Request, HTTPException, Depends
from jose import jwt, JWTError
from dotenv import load_dotenv
import os
load_dotenv()


SECRET_KEY=os.getenv('SECRET_KEY')
# Shared with chatbox_backend
JWT_ALGORITHM=os.getenv('JWT_ALGORITHM', 'HS256')


def verify_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # Optionally return payload if you want to use it
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
