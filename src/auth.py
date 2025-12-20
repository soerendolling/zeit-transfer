import os
from dotenv import load_dotenv

def load_credentials():
    """
    Load credentials from .env file.
    Raises ValueError if any required credential is missing.
    """
    load_dotenv()

    credentials = {
        "ZEIT_USER": os.getenv("ZEIT_USER"),
        "ZEIT_PASSWORD": os.getenv("ZEIT_PASSWORD"),
        "ZEIT_LOGIN_URL": os.getenv("ZEIT_LOGIN_URL", "https://login.zeit.de/"),
        "ZEIT_DOWNLOAD_URL": os.getenv("ZEIT_DOWNLOAD_URL", "https://epaper.zeit.de/abo/diezeit/"),
        "TOLINO_USER": os.getenv("TOLINO_USER"),
        "TOLINO_PASSWORD": os.getenv("TOLINO_PASSWORD"),
        "TOLINO_LOGIN_URL": os.getenv("TOLINO_LOGIN_URL", "https://webreader.mytolino.com/"),
    }

    missing = [key for key, value in credentials.items() if not value]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    return credentials
