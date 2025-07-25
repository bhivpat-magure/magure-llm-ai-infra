from fastapi import APIRouter, Depends,HTTPException
import uuid
from datetime import datetime
import requests
from sqlalchemy.orm import Session
from .. import models, schemas, database, crud , utils
import json




models.Base.metadata.create_all(bind=database.engine)
base_url = "http://ollama:11434/api/generate"

router = APIRouter(prefix="/api2")


@router.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate,db: Session = Depends(database.get_db)):
    
    print(f"Registering user with username: {user}")
    
    return crud.create_user(user,db)


@router.post("/chat_sessions", response_model=schemas.ChatSessionOut)
def create_chat(session: schemas.ChatSessionCreate, db: Session = Depends(database.get_db)):
    
    return crud.create_chat_session(session,db)



@router.post("/messages", response_model=schemas.MessageOut)
def post_message(message: schemas.MessageCreate, db: Session = Depends(database.get_db)):
    try:
        # Start a transaction manually
        user_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=message.chat_id,
            role = message.role.value if isinstance(message.role, schemas.RoleEnum) else message.role,
            user_id=message.user_id,
            content=message.content,
            created_at=datetime.utcnow()
        )
        
        
        print("<=======================================================>")
        print(f"User message to be saved: {user_msg}")
        print("<=======================================================>")  
        
        db.add(user_msg)
        db.flush()  # ✅ Temporarily saves but doesn’t commit yet
        
        print(f"User message saved: {user_msg.content}")

        # Fetch all messages for the chat
        past_messages = crud.get_messages_by_chat_id(message.chat_id, db)
        


        context = "\n".join([f"{utils.normalize_role(msg.role)}: {msg.content}" for msg in past_messages])

        print("<================================>")
        print(f"Context for Ollama: {context}")
        print("<================================>")
        # Call Ollama
        response = requests.post(
            base_url,
            json={
                "model": "llama3",
                "prompt": context,
                "stream": False
            }
        )

        if response.status_code != 200:
            db.rollback()  
            raise HTTPException(status_code=500, detail="Ollama generation failed")

        assistant_text = response.json()["response"]

        assistant_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=message.chat_id,
            role="assistant",
            user_id=message.user_id,  # or None if assistant has no user_id
            content=assistant_text,
            created_at=datetime.utcnow()
        )

        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        print("<===================>", assistant_msg.content)

        return assistant_msg

    except Exception as e:
        db.rollback()  # ✅ Roll back if anything fails
        raise HTTPException(status_code=500, detail=f"Failed to handle message: {e}")


@router.get("/chat_sessions/{user_id}", response_model=list[schemas.ChatSessionOut])
def get_user_chats(user_id: str, db: Session = Depends(database.get_db)):
    return crud.get_chat_sessions_by_user(user_id,db)

@router.get("/messages/{chat_id}", response_model=list[schemas.MessageOut])
def get_chat_messages(chat_id: str, db: Session = Depends(database.get_db)):
    return crud.get_messages_by_chat_id(chat_id,db)
