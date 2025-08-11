# Add these imports at the top of your router file
from fastapi import File, UploadFile, Form
import base64
import mimetypes
import os  # For API keys
from fastapi import APIRouter, Depends, HTTPException
import uuid
from datetime import datetime
import requests
from sqlalchemy.orm import Session
from .. import models, schemas, database, crud, utils

router = APIRouter(prefix="/api2/chat", tags=["Chat"])

# I've assumed you'll store API keys in environment variables for security
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# ... (your existing router and endpoints) ...

@router.post("/message-with-file-upload", response_model=schemas.MessageOut)
async def post_message_with_file(
        db: Session = Depends(database.get_db),
        # Use Form for text fields and UploadFile for the file
        chat_id: str = Form(...),
        user_id: str = Form(...),
        content: str = Form(...),
        modelType: str = Form(...),  # Received as string from form data
        file: UploadFile = File(...)
):
    """
    Accepts a message, a file, and a model type.
    1. Uploads the file to the specified service (OpenAI or Anthropic).
    2. Stores the file_id returned by OpenAI.
    3. Sends the user's prompt (content) along with the file reference.
    4. Saves the user message and assistant response to the database.
    """
    if modelType not in ["openai", "anthropic"]:
        raise HTTPException(status_code=422, detail="File upload is only supported for 'openai' or 'anthropic' models.")

    try:
        file_content = await file.read()
        filename = file.filename
        uploaded_file_id = None  # This will store the ID from OpenAI
        api_request_payload = {}
        api_url = ""
        api_headers = {}

        # --- Step 1: Handle file upload based on the model ---
        if modelType == "openai":
            if not OPENAI_API_KEY:
                raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

            # OpenAI requires a two-step process: upload file first, then use the ID
            upload_response = requests.post(
                "https://api.openai.com/v1/files",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={
                    'file': (filename, file_content, file.content_type),
                    'purpose': (None, 'vision'),
                }
            )
            if upload_response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"OpenAI file upload failed: {upload_response.text}")

            uploaded_file_id = upload_response.json()["id"]

            # Prepare the chat completion request
            api_url = "https://api.openai.com/v1/chat/completions"
            api_headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            api_request_payload = {
                "model": "gpt-4-vision-preview",  # or another model that supports vision
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": content},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{file.content_type};base64,{base64.b64encode(file_content).decode('utf-8')}"}
                            }
                        ]
                    }
                ],
                "max_tokens": 1024
            }

        elif modelType == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set.")

            # Anthropic handles image data directly in the message payload
            media_type, _ = mimetypes.guess_type(filename)
            if not media_type:
                media_type = "application/octet-stream"  # Fallback

            base64_data = base64.b64encode(file_content).decode("utf-8")

            api_url = "https://api.anthropic.com/v1/messages"
            api_headers = {
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            api_request_payload = {
                "model": "claude-3-opus-20240229",  # or another model that supports vision
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_data
                                }
                            },
                            {
                                "type": "text",
                                "text": content
                            }
                        ]
                    }
                ]
            }
            # NOTE: Anthropic's message API does not return a re-usable file ID.
            # The file data is sent with each relevant request.
            # We store the filename for reference.
            uploaded_file_id = f"anthropic-file:{filename}"

        # --- Step 2: Save the user's message to the database ---
        user_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            role="user",
            user_id=user_id,
            content=content,  # The text prompt
            file_id=uploaded_file_id,  # The ID from OpenAI or reference for Anthropic
            created_at=datetime.utcnow()
        )
        db.add(user_msg)
        db.flush()

        # --- Step 3: Send the request to the AI model ---
        response = requests.post(api_url, json=api_request_payload, headers=api_headers)

        if response.status_code != 200:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"{modelType.capitalize()} API call failed: {response.text}")

        # --- Step 4: Parse the response and save the assistant's message ---
        assistant_text = ""
        if modelType == "openai":
            assistant_text = response.json()["choices"][0]["message"]["content"]
        elif modelType == "anthropic":
            assistant_text = response.json()["content"][0]["text"]

        assistant_msg = models.Message(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            role="assistant",
            user_id=user_id,
            content=assistant_text,
            created_at=datetime.utcnow()
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        return assistant_msg

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to handle file message: {e}")