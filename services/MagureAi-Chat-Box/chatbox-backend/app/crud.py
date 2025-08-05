
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
import uuid

def create_user(user:schemas.UserCreate ,db: Session ):
    
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    db_user = models.User(
        username=user.username,
        password=user.password
    )
   
   
    print("The hash password is",db_user.password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_username( username: str , db: Session):
    return db.query(models.User).filter(models.User.username == username).first()

def create_chat_session(session: schemas.ChatSessionCreate, db: Session):
    db_session = models.ChatSession(**session.dict())
    
    user = get_chat_sessions_by_user(session.user_id, db)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    print(f"Creating chat session with title: {db_session.title}")
    
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_chat_sessions_by_user( user_id: str , db: Session):
    return db.query(models.ChatSession).filter(models.ChatSession.user_id == user_id).all()

def get_messages_by_chat_id( chat_id: str,db: Session):
    
    print("The chat_id is: ", chat_id)
    
    return db.query(models.Message).filter(models.Message.chat_id == chat_id).order_by(models.Message.created_at).all()

def create_message(db: Session, message: schemas.MessageCreate):
    msg = models.Message(id=str(uuid.uuid4()), **message.dict())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
