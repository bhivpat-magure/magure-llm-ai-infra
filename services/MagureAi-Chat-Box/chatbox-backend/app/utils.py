import uuid
import hashlib
from .schemas import RoleEnum
 
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
 
def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def normalize_role(role):
    return role.value if isinstance(role,RoleEnum) else role