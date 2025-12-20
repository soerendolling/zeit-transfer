# Zeit-Transfer

Automated tool to download "Die Zeit" EPUBs and upload them to Tolino Cloud.

## Features

- **Automated Download**: Logs into "Die Zeit" Premium (via Selenium) and downloads the latest EPUB.
- **Smart Download Check**: Tracks downloaded issues in `download_history.json` to prevent duplicates.
- **Cloud Upload**: Automatically uploads the EPUB to Tolino Webreader.
- **Test Mode**: Includes a `--test` flag to bypass history checks for local debugging.
- **Automated Execution**: Configured for daily execution via GitHub Actions.
- **Secure**: Uses environment variables for credentials.

## Prerequisites

- Python 3.9+
- A "Die Zeit" Premium subscription.
- A Tolino account (specifically Thalia DE linked).
- Chrome (for local Selenium runs).

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd zeit-transfer
   ```

2. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Configure credentials:
   Create a `.env` file in the root directory:
   ```
   ZEIT_USER=your_email@example.com
   ZEIT_PASSWORD=your_password
   ZEIT_LOGIN_URL=https://login.zeit.de/
   ZEIT_DOWNLOAD_URL=https://epaper.zeit.de/abo/diezeit/
   TOLINO_USER=your_tolino_email
   TOLINO_PASSWORD=your_tolino_password
   ```

## Usage

### Standard Run
Checks `download_history.json`. If the current issue date matches the last downloaded one, valid execution stops early ("SKIPPED").

```bash
python3 -m src.main
```

### Test Mode
Ignores the history check and forces a download/upload cycle. Useful for debugging or verifying fixes without resetting the history file manually.

```bash
python3 -m src.main --test
```

## GitHub Actions Automation

This repository includes a workflow `.github/workflows/daily_transfer.yml` that runs daily at **06:00 UTC**.
It handles:
1.  Checking out the code.
2.  Setting up Python and Chrome.
3.  Running the script.
4.  Committing the updated `download_history.json` back to the repository.

**Required GitHub Secrets:**
- `ZEIT_USER`
- `ZEIT_PASSWORD`
- `ZEIT_DOWNLOAD_URL`
- `ZEIT_LOGIN_URL`
- `TOLINO_USER`
- `TOLINO_PASSWORD`

## Troubleshooting

- **Login Failures**: The script uses `undetected-chromedriver` to bypass bot detection. If login fails, check the screenshots in the directory (if running locally) or the Action logs.
- **Timeouts**: The script uses smart `WebDriverWait` (up to 20s). If the site is exceptionally slow, these might need adjustment in `src/zeit_scraper.py` or `src/tolino_uploader.py`.

## Disclaimer

This tool is for personal use only. Use responsibly and respect the terms of service of the respective platforms.
