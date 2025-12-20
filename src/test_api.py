import os
import logging
from src.tolino_api import TolinoApiClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_api():
    print("=== Testing Tolino API Integration ===")
    
    # Initialize Client
    client = TolinoApiClient()
    
    # 1. Login / Token Check
    if not client.refresh_token:
        print("\n[!] No refresh token found.")
        print("    Function: client.login()")
        print("    Action: Opening browser for interactive login...")
        
        if client.login():
            print("\n[SUCCESS] Login successful! Token saved to 'tolino_token.json'.")
        else:
            print("\n[FAILED] Login failed.")
            return
    else:
        print("\n[OK] Refresh token found in 'tolino_token.json'.")

    # 2. Upload Check
    print("\n--- Testing Upload ---")
    
    # Find a file
    epub_files = [f for f in os.listdir("temp") if f.endswith(".epub")]
    if epub_files:
        file_path = os.path.join("temp", epub_files[0])
        print(f"File: {file_path}")
        print("Attempting upload...")
        
        if client.upload(file_path):
             print("\n[SUCCESS] API Upload completed successfully!")
             print("You can verify this in your Tolino Library.")
        else:
             print("\n[FAILED] API Upload failed.")
    else:
        print("\n[SKIP] No EPUB file found in temp/ directory to test upload.")

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_api()
