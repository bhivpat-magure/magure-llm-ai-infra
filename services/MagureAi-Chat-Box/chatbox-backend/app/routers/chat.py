from fastapi import APIRouter, Depends, HTTPException
import uuid
from datetime import datetime
import requests
from sqlalchemy.orm import Session
from .. import models, schemas, database, crud, utils

models.Base.metadata.create_all(bind=database.engine)

router = APIRouter(prefix="/api2/chat", tags=["Chat"])


@router.post("/chat_sessions", response_model=schemas.ChatSessionOut)
def create_chat(session: schemas.ChatSessionCreate, db: Session = Depends(database.get_db)):
    return crud.create_chat_session(session, db)


@router.post("/messages", response_model=schemas.MessageOut)
def post_message(message: schemas.MessageCreate, db: Session = Depends(database.get_db)):
    try:

        user_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=message.chat_id,
            role=message.role.value if isinstance(message.role, schemas.RoleEnum) else message.role,
            user_id=message.user_id,
            content=message.content,
            created_at=utils.get_current_time()
        )

        formatted_time = user_msg.created_at.strftime("%I:%M %p")

        print("THE TIME IS===================>", formatted_time)

        db.add(user_msg)
        db.flush()

        print(f"User message saved: {user_msg.content}")

        past_messages = crud.get_messages_by_chat_id(message.chat_id, db)

        if len(past_messages) == 1:
            # Update chat title if it's the first message
            print("Setting chat title to first user message")
            chat = utils.get_chat_by_id(message.chat_id, db)

            if not chat:
                raise HTTPException(status_code=404, detail="Chat session not found")

            chat.title = message.content  # Set title to first user message

            db.flush()

        model_type = message.modelType.value if isinstance(message.modelType, schemas.ModelType) else message.modelType

        context = utils.build_context(model_type, past_messages)

        query = utils.build_query(model_type, context)

        response = requests.post(
            query["url"],
            json=query["json"],
            headers=query.get("headers", {})
        )

        if response.status_code != 200:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"{model_type.capitalize()} generation failed")

        if model_type == "ollama":
            assistant_text = response.json().get("response", "")
        elif model_type == "openai":
            assistant_text = response.json()["choices"][0]["message"]["content"]
        elif model_type == "anthropic":
            assistant_text = response.json()["content"][0]["text"]
        else:
            raise HTTPException(status_code=422, detail=f"Unsupported model type: {model_type}")

        assistant_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=message.chat_id,
            role="assistant",
            user_id=message.user_id,  # or None if assistant has no user_id
            content=assistant_text,
            created_at=utils.get_current_time()
        )

        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        print("<===================>", assistant_msg.content)

        return assistant_msg


    except Exception as e:
        db.rollback()  # Roll back if anything fails
        raise HTTPException(status_code=500, detail=f"Failed to handle message: {e}")


@router.get("/chat_sessions/{user_id}", response_model=list[schemas.ChatSessionOut])
def get_user_chats(user_id: str, db: Session = Depends(database.get_db)):
    return crud.get_chat_sessions_by_user(user_id, db)


@router.get("/messages/{chat_id}", response_model=list[schemas.MessageOut])
def get_chat_messages(chat_id: str, db: Session = Depends(database.get_db)):
    return crud.get_messages_by_chat_id(chat_id, db)


@router.put("/chat_sessions/rename", response_model=schemas.ChatSessionOut)
def rename_chat_session(session: schemas.ChatSessionRename, db: Session = Depends(database.get_db)):
    print("Renaming chat session with ID:", session.chat_id)

    # Get the chat session to ensure it exists
    chat = utils.get_chat_by_id(session.chat_id, db)

    if not chat:
        raise HTTPException(status_code=404, detail="No such chat session exists")

    chat.title = session.title
    db.commit()
    db.refresh(chat)

    return chat


@router.delete("/chat_sessions/{chat_id}")
def delete_chat_session(chat_id: str, db: Session = Depends(database.get_db)):
    # Get the chat session to ensure it exists
    chat = utils.get_chat_by_id(chat_id, db)

    if not chat:
        raise HTTPException(status_code=404, detail="No such chat session exists")

    db.delete(chat)
    db.commit()

    return {"detail": "Chat session deleted successfully"}