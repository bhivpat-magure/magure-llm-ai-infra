import os
from fastapi import APIRouter, Depends, File, Form,HTTPException, UploadFile
import uuid
import requests
from sqlalchemy.orm import Session
from .. import models, schemas, database, crud , utils
from . import file_handler


models.Base.metadata.create_all(bind=database.engine)

router = APIRouter(prefix = "/api2/chat" , tags = ["Chat"])

@router.post("/chat_sessions", response_model=schemas.ChatSessionOut)
def create_chat(session: schemas.ChatSessionCreate, db: Session = Depends(database.get_db)):
    return crud.create_chat_session(session,db)


@router.post("/messages", response_model=schemas.MessageOut)
def post_message(message: schemas.MessageCreate, db: Session = Depends(database.get_db)):
    try:
        
        user_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=message.chat_id,
            role = message.role.value if isinstance(message.role, schemas.RoleEnum) else message.role,
            content=message.content,
            created_at=utils.get_current_time()  
        )
                
        db.add(user_msg)
        db.flush() 
        
        print(f"User message saved: {user_msg.created_at}")
        
        past_messages = crud.get_messages_by_chat_id(message.chat_id, db)
        
        
        if len(past_messages) == 1:
            # Update chat title if it's the first message
            print("Setting chat title to first user message")
            chat = crud.get_chat_by_id(message.chat_id, db)

            if not chat:
                raise HTTPException(status_code=404, detail="Chat session not found")

            chat.title = message.content  # Set title to first user message
            
            db.flush()

        model_type = message.modelType.value if isinstance(message.modelType, schemas.ModelType) else message.modelType
        
        context = utils.build_context(model_type,past_messages)
            
        query = utils.build_query(model_type,context)
    
        
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

# Create a prompt + file upload endpoint which will take in a file, prompt, chatID and model type 
# Save the file in a temporary location which will be changed during production
# Get the location of the file at saved location
# Then we will have a File URL, File Name and chat ID, we need to write that in the DB
# We need to Extract the Chat History from DB
# Just like the above function post_message, we will extarct the context and query the model
# Then we will return the response from the model
@router.post("/upload_and_chat")
async def upload_and_chat(
    chat_id: str = Form(...),
    model_type: str = Form(...),
    prompt: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db)
):
    try:
        UPLOAD_DIR=os.getcwd() + '/uploads'
        # Save the uploaded file temporarily
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        print(file_location)
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())

        # Save file information to the database
        file_record = models.File(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            file_name=file.filename,
            file_url=file_location, # This will be changed in production
            created_at=utils.get_current_time()
        )
        db.add(file_record)
        db.flush()

        # Create and save user message with prompt
        # user_msg = models.Message(
        #     id=str(uuid.uuid4()),
        #     chat_id=chat_id,
        #     role="user",
        #     content=prompt,
        #     created_at=utils.get_current_time()
        # )
        # db.add(user_msg)
        # db.flush()

        # # Get chat history from the database
        past_messages = crud.get_messages_by_chat_id(chat_id, db)

        # Build context and query for the model
        context = utils.build_context(model_type, past_messages)
        # You'll need to update utils.build_query to handle file data
        # For now, let's assume the prompt and context are sufficient
        query = utils.build_query(model_type, context)

        # Query the model
        response = file_handler.process_file_with_llm(model_type, file_location, prompt)
        
        return models.Message(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            role="assistant",
            content=response,
            created_at=utils.get_current_time()
        )

        # if response.status_code != 200:
        #     db.rollback()
        #     raise HTTPException(status_code=500, detail=f"{model_type.capitalize()} generation failed")

        # Extract assistant's response
        # if model_type == "ollama":
        #     assistant_text = response.json().get("response", "")
        # elif model_type == "openai":
        #     assistant_text = response.json()["choices"][0]["message"]["content"]
        # elif model_type == "anthropic":
        #     assistant_text = response.json()["content"][0]["text"]
        # else:
        #     raise HTTPException(status_code=422, detail=f"Unsupported model type: {model_type}")

        # # Save assistant's response to the database
        # assistant_msg = models.Message(
        #     id=str(uuid.uuid4()),
        #     chat_id=chat_id,
        #     role="assistant",
        #     content=assistant_text,
        #     created_at=utils.get_current_time()
        # )
        # db.add(assistant_msg)
        # db.commit()
        # db.refresh(assistant_msg)

        # # Clean up the temporary file (optional but good practice)
        # os.remove(file_location)

        # return {"assistant_response": assistant_msg.content}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to handle file upload and chat: {e}")




@router.put("/chat_sessions/rename",response_model=schemas.chatSessionRenameOut)
def rename_chat_session(session : schemas.ChatSessionRename, db: Session = Depends(database.get_db)):
    print("Renaming chat session with ID:", session.chat_id)
    
    # Get the chat session to ensure it exists
    chat = crud.get_chat_by_id(session.chat_id, db)
    
    if not chat:
        raise HTTPException(status_code=404, detail="No such chat session exists")
    
    chat.title = session.title
    chat.updated_at = utils.get_current_time()
    db.commit()
    db.refresh(chat)
    
    chat_rename_response = schemas.chatSessionRenameOut(
        title=chat.title,
        chat_id=chat.id,
        updated_at=chat.updated_at
    )
    
    return chat_rename_response


@router.get("/messages/{chat_id}", response_model=schemas.MessageOutWithChatId)
def get_chat_messages(chat_id: str, db: Session = Depends(database.get_db)):
    return crud.get_messages_by_chat_id(chat_id,db,isFileRequest= True)


@router.get("/chat_sessions/user/{user_id}", response_model=list[schemas.ChatSessionOutWithFiles])
def get_user_chats(user_id: str, db: Session = Depends(database.get_db)):
    return crud.get_chat_sessions_by_user(user_id,db)


@router.delete("/chat_sessions/delete/{chat_id}")
def delete_chat_session(chat_id: str, db: Session = Depends(database.get_db)):
        
    chat = crud.get_chat_by_id(chat_id, db)
    
    if not chat:
        raise HTTPException(status_code=404, detail="No such chat session exists")
    
    db.delete(chat)
    db.commit()
    
    return {"detail": "Chat session deleted successfully"}
