
from fastapi import HTTPException
from sqlalchemy.orm import Session , joinedload
from app import models, schemas , utils
import uuid

def create_user(user:schemas.UserCreate ,db: Session ):
    
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    db_user = models.User(
        username=user.username,
        password=user.password,
        created_at=utils.get_current_time()
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_username( username: str , db: Session):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(user_id: str, db: Session):
    return db.query(models.User).filter(models.User.id == user_id).first()

def create_chat_session(session: schemas.ChatSessionCreate, db: Session):
        
    # user = get_user_by_id(session.user_id, db)
    
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found")
    
    db_session = models.ChatSession(
        title=session.title,
        user_id=session.user_id,
        created_at=utils.get_current_time()
    )
    
    print(f"Creating chat session with title: {db_session.title}")
    
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_chat_sessions_by_user( user_id: str , db: Session):
    
    print(f"Fetching chat sessions for user: {user_id}")
    
    sessions = (
        db.query(models.ChatSession)
        .options(joinedload(models.ChatSession.files))
        .filter(models.ChatSession.user_id == user_id)
        .all()
    )

    response = []
    for session in sessions:
        
        first_file = session.files[0] if session.files else None
        response.append(schemas.ChatSessionOut(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            file_url=first_file.file_url if first_file else None,
            file_name=first_file.file_name if first_file else None
        ))

    return response



def get_messages_by_chat_id( chat_id: str,db: Session):
    
    print("The chat_id is: ", chat_id)
    
    return db.query(models.Message).filter(models.Message.chat_id == chat_id).order_by(models.Message.created_at).all()



def get_chat_by_id(chat_id: str, db):
    chat = db.query(models.ChatSession).filter(models.ChatSession.id == chat_id).first()
    return chat
