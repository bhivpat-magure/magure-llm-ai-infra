# test_openai_key.py
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists in the same directory
# This is useful if you want to keep your key in .env even for this test script
load_dotenv()

# --- IMPORTANT: Replace with your actual OpenAI API Key ---
# Option 1: Get from environment variable (recommended if using .env for this script)
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY"))
# OPENAI_API_KEY = "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"
print(OPENAI_API_KEY)
# PROJECT_ID = "proj-fvhJF9ddjqf7hUsER5FfnjjvMogDyqGESysBKhDAMSXw5eq_MPC_5iIICmQV656j3Q-SQ7YC1_T3BlbkFJVcJGpfWw4T2OcTKd0cHWl1Wt0JGqbDM-ziFkR3eZrPlQwLyHK7qyvA8SwqM3jMXOP31IfhP9cA"

# Option 2: Hardcode directly (only for quick test, remove after)
# OPENAI_API_KEY = "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"

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY not found. Please set it in your .env file or hardcode it for testing.")
    exit()

try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ]
    )
    print(completion)

    # # Make a small, cheap API call to verify the key
    # # Listing models is a good way to test authentication without generating content
    # response = client.models.list()
    # print(response)

    print("\n--- OpenAI API Key Test Result ---")
    print("OpenAI API Key is VALID!")
    # print(f"Successfully listed {len(response.data)} models.")
    # You can print some model IDs to confirm:
    # for model in response.data[:5]:
    #     print(f"- {model.id}")

except Exception as e:
    print("\n--- OpenAI API Key Test Result ---")
    print("OpenAI API Key is INVALID or there's an issue with your account.")
    print(f"Error details: {e}")
    if "401" in str(e) or "invalid_api_key" in str(e):
        print("\nPossible reasons for 401/invalid_api_key:")
        print("1. The key itself is incorrect (typo, expired, revoked).")
        print("2. Your OpenAI account might need billing information added/updated.")
        print("3. You might have hit rate limits (less likely for a simple list call).")
    elif "No such model" in str(e):
        print("This error usually means the model specified in the API call (if any) doesn't exist.")
    else:
        print("Check your internet connection or OpenAI's service status.")