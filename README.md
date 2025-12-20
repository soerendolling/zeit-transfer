# Zeit-Transfer

Automated tool to download "Die Zeit" EPUBs and upload them to Tolino Cloud.

## Features

- **Automated Download**: Logs into "Die Zeit" Premium and downloads the latest EPUB.
- **State Management**: Tracks downloaded issues to avoid duplicates.
- **Cloud Upload**: Automatically uploads the EPUB to Tolino Webreader.
- **Secure**: Uses environment variables for credentials.

## Prerequisites

- Python 3.10+
- A "Die Zeit" Premium subscription.
- A Tolino account (and linked bookseller account).

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd zeit-transfer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. Configure credentials:
   Copy `.env.example` to `.env` and fill in your details.
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```
   ZEIT_USER=your_email@example.com
   ZEIT_PASSWORD=your_password
   TOLINO_USER=your_tolino_email
   TOLINO_PASSWORD=your_tolino_password
   ```

## Usage

Run the script manually:

```bash
python src/main.py
```

## Automation

You can set up a cron job to run this script weekly (e.g., Wednesday evening).

```bash
# Example: Run every Wednesday at 19:00
0 19 * * 3 /path/to/python /path/to/zeit-transfer/src/main.py >> /path/to/zeit-transfer/cron.log 2>&1
```

## Troubleshooting

- **Login Failures**: Check `zeit_transfer.log` for details. If the website layout changes, the selectors in `src/zeit_scraper.py` or `src/tolino_uploader.py` might need updating.
- **Headless Mode**: To debug browser interactions, set `headless=False` in the `ZeitScraper` and `TolinoUploader` classes.

## Disclaimer

This tool is for personal use only. Use responsibly and respect the terms of service of the respective platforms.
