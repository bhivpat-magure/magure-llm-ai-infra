from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .. import schemas, crud
from ..utils import create_access_token,verify_password,get_password_hash


def login_user(user: schemas.UserLogin, db: Session):
    
        
    db_user = crud.get_user_by_username(user.username, db)
    

    verified_password = verify_password(user.password,db_user.password)    
    
    
    print("<============== The verified passward is ============>" , verified_password)
    
    
    if not db_user or not verified_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": str(db_user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(db_user.id),   
        "username": db_user.username  
    }

def register_user(user: schemas.UserCreate, db: Session):
    user.password = get_password_hash(user.password)
    return crud.create_user(user, db)


