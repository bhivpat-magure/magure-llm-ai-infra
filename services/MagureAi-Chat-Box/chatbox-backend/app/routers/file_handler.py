
import os
import sys
import base64
from pathlib import Path
from openai import OpenAI
from anthropic import Anthropic
from reportlab.pdfgen import canvas
import magic # Requires python-magic library
from ..config import settings

# Initialize API clients
openai_client = OpenAI(api_key = settings.OPENAI_API_KEY)
anthropic_client = Anthropic()


def get_base64_file(file_path: str) -> str:
    """Encodes a file to a Base64 string."""
    try:
        with open(file_path, "rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")
    except FileNotFoundError:
        return None

def get_mime_type(file_path: str) -> str:
    """Determines the MIME type of a file using python-magic."""
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    except Exception:
        return "application/octet-stream"

def process_file_with_llm(model_choice: str, file_path: str, prompt: str) -> str:
    """
    Dynamically processes a file with the selected LLM based on file type.
    """
    mime_type = get_mime_type(file_path)
    base64_file = get_base64_file(file_path)

    if not base64_file:
        return "Error: File not found or could not be encoded."

    # --- OpenAI Execution ---
    if model_choice.lower() == "openai":
        """
    Processes a file using the OpenAI Assistants API with the file_search tool.
    
    Args:
        file_path (str): The local path to the file to be processed.
        prompt (str): The prompt for the LLM.

    Returns:
        str: The response from the LLM based on the document content.
    """
        try:
            with open(file_path, "rb") as f:
                uploaded_file = openai_client.files.create(file=f, purpose="assistants")
            
            file_id = uploaded_file.id
            
            vector_store = openai_client.vector_stores.create(
                name="My Document Store",
                file_ids=[file_id]
            )

            vector_store_id = vector_store.id
            print(f"Vector store created with ID: {vector_store_id}")
            assistant = openai_client.beta.assistants.create(
                name="Document Analyzer",
                instructions="You are a helpful assistant that analyzes documents and answers questions based on their content.",
                model="gpt-4o",
                tools=[{"type": "file_search"}]
            )
            assistant_id = assistant.id
            thread = openai_client.beta.threads.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "attachments": [
                            { "file_id": file_id, "tools": [{"type": "file_search"}] }
                        ]
                    }
                ]
            )
            thread_id = thread.id
            run = openai_client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=assistant_id
            )
            messages = openai_client.beta.threads.messages.list(thread_id=thread_id, run_id=run.id)
            
            if messages.data:
                response_content = messages.data[0].content[0].text.value
            else:
                response_content = "Error: No response found."
            openai_client.beta.threads.delete(thread_id=thread_id)
            openai_client.beta.assistants.delete(assistant_id=assistant_id)
            openai_client.vector_stores.delete(vector_store_id=vector_store_id)
            openai_client.files.delete(file_id=file_id)
            
            return response_content

        except Exception as e:
            # A more robust solution would include specific error handling
            return f"An error occurred: {str(e)}"

    # --- Anthropic Execution ---
    elif model_choice.lower() == "anthropic":
        # Anthropic's Messages API can handle images and PDFs directly.
        if mime_type.startswith("image/") or mime_type == "application/pdf":
            content_type = "image" if mime_type.startswith("image/") else "document"
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": content_type, "source": {"type": "base64", "media_type": mime_type, "data": base64_file}}
                ]}
            ]
            response = anthropic_client.messages.create(model="claude-3-5-sonnet-20241022", max_tokens=1024, messages=messages)
            print(response.content[0].text)
            return response.content[0].text
        
        # For other documents, we send the content as text
        elif mime_type.startswith("text/"):
            with open(file_path, "r") as f:
                file_content = f.read()
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "text", "text": f"\n\nFile Content:\n{file_content}"}
                ]}
            ]
            response = anthropic_client.messages.create(model="claude-3-opus-20240229", max_tokens=1024, messages=messages)
            return response.content[0].text
        else:
            return "❌ Anthropic's Messages API does not support this file type for direct analysis."

    else:
        return "❌ Invalid model choice. Please use 'openai' or 'anthropic'."

def create_dummy_files():
    """Creates dummy files for testing."""
    Path("test_image.jpeg").touch()
    with open("test_image.jpeg", "wb") as f: f.write(b"dummy image data")

    c = canvas.Canvas("test_document.pdf")
    c.drawString(100, 750, "This is a test PDF document.")
    c.save()

    with open("test_document.txt", "w") as f:
        f.write("This is a simple text document to test the chat model.")

def cleanup_dummy_files():
    """Removes dummy files after testing."""
    for file in ["test_image.jpeg", "test_document.pdf", "test_document.txt"]:
        if os.path.exists(file):
            os.remove(file)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python script.py <model_choice> <file_path> <prompt>")
        print("Example: python script.py anthropic test_document.pdf 'Summarize this PDF'")
        sys.exit(1)

    model_choice, file_path, prompt = sys.argv[1], sys.argv[2], sys.argv[3]

    print("--- Creating dummy files for testing... ---")
    create_dummy_files()
    
    print(f"\n--- Running test with {model_choice.upper()} on {file_path} ---")
    response = process_file_with_llm(model_choice, file_path, prompt)
    print("\n--- Model Response ---")
    print(response)

    print("\n--- Cleaning up dummy files... ---")
    cleanup_dummy_files()