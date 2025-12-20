import os
import sys
import logging
import glob
import argparse
from dotenv import load_dotenv
from src.zeit_scraper import ZeitScraper
from src.tolino_uploader import TolinoUploader

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

def load_environment():
    load_dotenv()
    required_vars = ["ZEIT_USER", "ZEIT_PASSWORD", "ZEIT_LOGIN_URL", "ZEIT_DOWNLOAD_URL", "TOLINO_USER", "TOLINO_PASSWORD"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        return False
    return True

def get_latest_file(directory, extension=".epub"):
    files = glob.glob(os.path.join(directory, f"*{extension}"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def main():
    parser = argparse.ArgumentParser(description="Zeit Transfer Script")
    parser.add_argument("--test", action="store_true", help="Run in test mode (ignore history check)")
    args = parser.parse_args()

    logger.info("Starting Zeit-Transfer...")
    
    if not load_environment():
        sys.exit(1)

    temp_dir = "temp"
    
    # Initialize Scraper
    scraper = ZeitScraper(
        username=os.getenv("ZEIT_USER"),
        password=os.getenv("ZEIT_PASSWORD"),
        login_url=os.getenv("ZEIT_LOGIN_URL"),
        download_url=os.getenv("ZEIT_DOWNLOAD_URL"),
        download_dir=temp_dir,
        test_mode=args.test
    )

    # 1. Download Step
    epub_path = None
    existing_file = get_latest_file(temp_dir)
    
    if existing_file:
        logger.info(f"Found existing file in temp: {os.path.basename(existing_file)}. Skipping download and retrying upload.")
        epub_path = existing_file
    else:
        # 2. Download latest issue
        logger.info("Checking for new issue...")
        epub_path = scraper.download_latest_issue()
        
        if epub_path == "SKIPPED":
            logger.info("Scraper reported no new issue. Exiting.")
            return # Success exit for skipped

        if not epub_path:
            logger.error("Download failed.")
            sys.exit(1) # Fail exit

    filename = os.path.basename(epub_path)
    logger.info(f"Processing issue: {filename}")

    # 2. Upload Step
    uploader = TolinoUploader(
        username=os.getenv("TOLINO_USER"),
        password=os.getenv("TOLINO_PASSWORD"),
        login_url="https://webreader.mytolino.com/"
    )

    if uploader.upload_epub(epub_path):
        logger.info(f"Successfully uploaded {filename} to Tolino.")
        # Cleanup
        try:
            os.remove(epub_path)
            logger.info(f"Cleaned up temporary file: {epub_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file: {e}")
    else:
        logger.error(f"Failed to upload {filename} to Tolino.")
        logger.warning(f"Upload failed. File preserved at: {epub_path}")
        sys.exit(1) # Fail exit

    logger.info("Zeit-Transfer finished.")

if __name__ == "__main__":
    main()
