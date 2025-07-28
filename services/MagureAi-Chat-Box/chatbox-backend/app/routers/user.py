from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..schemas import UserCreate, UserOut, UserLogin,TokenResponse
from ..database import get_db
from ..auth.auth import register_user, login_user

router = APIRouter(prefix="/api2/auth", tags=["Auth"])

@router.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    return register_user(user, db)

@router.post("/login",response_model = TokenResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):    
    return login_user(user, db)
