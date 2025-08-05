from jose import jwt, JWTError
from flask import request, jsonify
import os



from functools import wraps

# Replace this with your actual secret and algorithm
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"


def get_current_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Missing token"}), 401
    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Missing user_id")
        return user_id  # or return a user object via DB lookup
    except JWTError:
        return jsonify({"detail": "Invalid token"}), 401




def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # JWT is passed in the request header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"message": "Token is missing"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            # Optionally, you can store user info in request context
            request.user = data
        except JWTError:
            return jsonify({"message": "Token is invalid"}), 401

        return f(*args, **kwargs)

    return decorated
