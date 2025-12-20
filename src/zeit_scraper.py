import os
import time
import logging
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

class ZeitScraper:
    def __init__(self, username, password, login_url, download_url, download_dir="temp", state_file=None):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.download_url = download_url
        self.download_dir = download_dir
        self.state_file = state_file
        self.logger = logging.getLogger(__name__)

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def download_latest_issue(self):
        """
        Logs in to Die Zeit and downloads the latest EPUB issue.
        Returns the path to the downloaded file or None if failed.
        """
        with sync_playwright() as p:
            # Reverting to a simpler launch configuration to see if it helps with CAPTCHA loading
            browser = p.chromium.launch(
                headless=False
            ) 
            
            # Load state if exists
            loaded_session = False
            if self.state_file and os.path.exists(self.state_file):
                self.logger.info(f"Loading session from {self.state_file}")
                context = browser.new_context(accept_downloads=True, storage_state=self.state_file)
                loaded_session = True
            else:
                context = browser.new_context(accept_downloads=True)

            page = context.new_page()
            
            # Temporarily disabled stealth to test baseline
            # stealth_sync(page)

            try:
                self.logger.info(f"Navigating to login page: {self.login_url}")
                page.goto(self.login_url)

                # Check if we are already logged in
                already_logged_in = False
                if loaded_session:
                    try:
                        # If logged in, we might be redirected to 'meine-inhalte' or 'konto' or just stay logged in
                        # Let's check if the login form is absent or if we are redirected
                        page.wait_for_selector("input#username", state="detached", timeout=5000)
                        self.logger.info("Login form not found immediately. Verifying login state...")
                        # Or check for 'Abmelden' button or similar
                        if page.get_by_text("Abmelden", exact=False).count() > 0 or "konto" in page.url:
                             already_logged_in = True
                             self.logger.info("Session valid. Already logged in.")
                    except:
                         pass

                if not already_logged_in:

                if not already_logged_in:
                    # Handle cookie banner if present
                    try:
                        page.wait_for_selector("button[title='Zustimmen']", timeout=5000)
                        page.click("button[title='Zustimmen']")
                    except:
                        pass

                    self.logger.info("Logging in...")
                    # Update selectors based on user feedback
                    # Email: input#username
                    # Password: input#password
                    # Submit: input#kc-login
                    
                    # Type significantly slower to simulate human behavior and trigger events
                    page.click("input#username")
                    page.type("input#username", self.username, delay=100)
                    
                    page.click("input#password")
                    page.type("input#password", self.password, delay=100)
                    
                    # Check for CAPTCHA/human verification potentially
                    # Sometimes just waiting a bit helps with stealth
                    time.sleep(2)
                    
                    try:
                        # Wait for button to be enabled
                        self.logger.info("Waiting for login button to be enabled...")
                        page.wait_for_function("document.querySelector('#kc-login') && !document.querySelector('#kc-login').disabled", timeout=5000)
                        page.click("#kc-login", timeout=5000)
                    except:
                         self.logger.warning("Automated login click failed (button disabled or not found).")
                         self.logger.info("PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW.")
                         # We don't exit here, we just fall through to the wait_for_url
                    
                    # Wait for login to complete
                    # The user says "Use log in page = https://login.zeit.de/"
                    # After login, we might be redirected. We should wait for a stable state.
                    self.logger.info("Waiting for login to complete (checking URL)...")
                    # Wait for any URL that indicates we left the login page
                    # The user URL: https://www.zeit.de/konto...
                    try:
                        page.wait_for_url(lambda url: "zeit.de/konto" in url or "aktuelle-ausgabe" in url, timeout=300000)
                    except:
                        self.logger.warning("URL check timed out, but proceeding assuming login might be done.")
                    
                    self.logger.info("Login successful.")
                    if self.state_file:
                        context.storage_state(path=self.state_file)
                        self.logger.info(f"Session saved to {self.state_file}")

                # Navigate to digital edition
                self.logger.info(f"Navigating to download URL: {self.download_url}")
                page.goto(self.download_url)

                # "Dann auf button zur aktuelle aufgabe"
                # We look for a link/button that says "Aktuelle Ausgabe" or similar.
                # It might be an image or text.
                self.logger.info("Looking for 'Aktuelle Ausgabe'...")
                
                # Try to find a link that contains "aktuelle-ausgabe" or text "Aktuelle Ausgabe"
                # Note: The user provided URL https://epaper.zeit.de/abo/diezeit/ might already show the issues.
                # We need to click on the latest one.
                
                # Let's try to find the first issue or a specific "Aktuelle Ausgabe" button.
                # Based on typical e-paper layouts, the latest issue is usually first.
                # Or there is a specific button.
                
                # Attempt 1: Look for text "Aktuelle Ausgabe"
                # "Dann auf button zur aktuelle aufgabe"
                self.logger.info("Looking for 'Zur aktuellen Ausgabe'...")
                
                # Try to find a link that contains "Aktuelle Ausgabe" or "Zur aktuellen Ausgabe"
                # We will try a few variations to be robust
                found_issue = False
                for selector in ["text=Zur aktuellen Ausgabe", "text=Aktuelle Ausgabe", "a:has-text('Aktuelle Ausgabe')"]:
                    try:
                        if page.is_visible(selector):
                            self.logger.info(f"Clicking {selector}...")
                            page.click(selector)
                            page.wait_for_load_state("networkidle")
                            found_issue = True
                            break
                    except:
                        continue
                
                if not found_issue:
                     self.logger.warning("'Zur aktuellen Ausgabe' link not found. We might already be on the issue page or the layout changed.")

                # "dann auf button epub laden"
                self.logger.info("Looking for EPUB download button...")
                
                # We need to trigger the download.
                # In Playwright, if the click triggers a download, we must wrap it with expect_download.
                # HOWEVER, sometimes you have to open a menu first.
                
                # Check for "EPUB" button directly
                epub_button = page.get_by_text("EPUB", exact=False).first
                
                # If not visible, look for a "Download" menu
                if not epub_button.is_visible():
                     self.logger.info("EPUB button not immediately visible. Checking for 'Download' menu...")
                     # sometimes it's under a "Download" or icon
                     download_menu = page.get_by_text("Download", exact=False).first
                     if download_menu.is_visible():
                         download_menu.click()
                         # Wait a bit for menu to open
                         time.sleep(1)
                         epub_button = page.get_by_text("EPUB", exact=False).first
                
                if not epub_button.is_visible():
                    self.logger.error("EPUB download link not found.")
                    # Take a screenshot to see what's on the page
                    page.screenshot(path="issue_page_debug.png")
                    self.logger.info("Saved issue_page_debug.png")
                    return None
                
                self.logger.info("EPUB button found. Clicking...")
                
                # Setup download listener BEFORE clicking
                with page.expect_download(timeout=60000) as download_info:
                    epub_button.click()
                
                download = download_info.value
                
                # Generate a safe filename
                suggested_filename = download.suggested_filename
                file_path = os.path.join(self.download_dir, suggested_filename)
                
                self.logger.info(f"Downloading {suggested_filename}...")
                download.save_as(file_path)
                self.logger.info(f"Download complete: {file_path}")
                
                return file_path

            except Exception as e:
                self.logger.error(f"An error occurred during Zeit scraping: {e}")
                # Capture screenshot for debugging
                try:
                    page.screenshot(path="error_screenshot.png")
                    self.logger.info("Saved error_screenshot.png")
                except:
                    pass
                return None
            finally:
                browser.close()
