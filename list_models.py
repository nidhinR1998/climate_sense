import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API key
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("ERROR: GOOGLE_API_KEY not found in .env file.")
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        print("Checking for available models...")

        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")

    except Exception as e:
        print(f"--- FAILED ---")
        print(f"An error occurred: {e}")
        print("This often means your API key is wrong OR your library is very old.")

print("...Check complete.")