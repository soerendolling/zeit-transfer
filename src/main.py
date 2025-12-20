import os
import json
import logging
import shutil
from datetime import datetime
from src.auth import load_credentials
from src.zeit_scraper import ZeitScraper
from src.tolino_uploader import TolinoUploader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("zeit_transfer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"downloaded_issues": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def main():
    logger.info("Starting Zeit-Transfer...")

    try:
        credentials = load_credentials()
    except ValueError as e:
        logger.error(str(e))
        return

    state = load_state()
    
    scraper = ZeitScraper(
        credentials["ZEIT_USER"], 
        credentials["ZEIT_PASSWORD"],
        credentials["ZEIT_LOGIN_URL"],
        credentials["ZEIT_DOWNLOAD_URL"],
        state_file="zeit_state.json"
    )
    
    # 1. Check for existing file in temp (retry mode)
    # If there is a file in temp that hasn't been marked as processed, try to upload it.
    existing_files = [f for f in os.listdir("temp") if f.endswith(".epub")]
    if existing_files:
        file_path = os.path.join("temp", existing_files[0])
        filename = existing_files[0]
        logger.info(f"Found existing file in temp: {filename}. Skipping download and retrying upload.")
    else:
        # 2. Download latest issue
        logger.info("Checking for new issue...")
        file_path = scraper.download_latest_issue()
        
        if not file_path:
            logger.info("No file downloaded or error occurred.")
            return

        filename = os.path.basename(file_path)
    
    # 3. Check if already processed (uploaded)
    if filename in state["downloaded_issues"]:
        logger.info(f"Issue {filename} already processed (uploaded). Skipping.")
        # If it's in state but still in temp, we should delete it.
        if os.path.exists(file_path):
             os.remove(file_path)
             logger.info(f"Deleted already processed file from temp: {file_path}")
        return

    logger.info(f"Processing issue: {filename}")

    # 4. Upload to Tolino
    uploader = TolinoUploader(
        credentials["TOLINO_USER"], 
        credentials["TOLINO_PASSWORD"],
        credentials["TOLINO_LOGIN_URL"],
        state_file="tolino_state.json"
    )
    success = uploader.upload_epub(file_path)

    if success:
        logger.info(f"Successfully uploaded {filename} to Tolino.")
        state["downloaded_issues"].append(filename)
        save_state(state)
    else:
        logger.error(f"Failed to upload {filename} to Tolino.")

    # 4. Cleanup
    if os.path.exists(file_path):
        if success:
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
        else:
             logger.warning(f"Upload failed. File preserved at: {file_path}")

    logger.info("Zeit-Transfer finished.")

if __name__ == "__main__":
    main()
