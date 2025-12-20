import os
import time
import logging
import glob
import json
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ZeitScraper:
    def __init__(self, username, password, login_url, download_url, download_dir="temp", history_file="download_history.json"):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.download_url = download_url
        self.download_dir = os.path.abspath(download_dir)
        self.history_file = history_file
        self.logger = logging.getLogger(__name__)

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_history(self, issue_id):
        history = self.load_history()
        history['last_issue_id'] = issue_id
        history['last_download_time'] = time.time()
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
            self.logger.info(f"Updated history with issue: {issue_id}")
        except Exception as e:
            self.logger.error(f"Failed to save history: {e}")

    def take_screenshot(self, driver, name):
        try:
            filename = f"{name}_{int(time.time())}.png"
            driver.save_screenshot(filename)
            self.logger.info(f"Saved screenshot: {filename}")
        except:
            pass

    def download_latest_issue(self):
        """
        Logs in to Die Zeit and downloads the latest EPUB issue using Selenium.
        Returns the path to the downloaded file or None if failed OR if already processed.
        """
        self.logger.info("Starting Zeit Scraper (Selenium)...")
        driver = None
        
        try:
            # Configure Chrome Options for Download
            options = uc.ChromeOptions()
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "plugins.always_open_pdf_externally": True 
            }
            options.add_experimental_option("prefs", prefs)
            
            # Initialize Driver
            driver = uc.Chrome(use_subprocess=True, options=options)
            driver.set_window_size(1280, 800)
            
            wait = WebDriverWait(driver, 20)
            
            # --- Login Phase ---
            self.logger.info(f"Navigating to login page: {self.login_url}")
            driver.get(self.login_url)
            time.sleep(3)

            # Detect Login State
            needs_login = False
            try:
                if len(driver.find_elements(By.CSS_SELECTOR, "input#username")) > 0:
                    needs_login = True
                    self.logger.info("Login form detected.")
                else:
                    self.logger.info("Login form NOT found. Checking for active session indicators...")
                    if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Abmelden') or contains(text(), 'Konto')]")) > 0:
                        self.logger.info("Active session detected.")
                        needs_login = False
                    else:
                        needs_login = True
            except:
                needs_login = True

            if needs_login:
                try:
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='Zustimmen']")))
                    cookie_btn.click()
                except:
                    pass
                
                try:
                    self.logger.info("Entering credentials...")
                    email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input#username")))
                    email_input.click()
                    email_input.clear()
                    email_input.send_keys(self.username)
                    
                    pass_input = driver.find_element(By.CSS_SELECTOR, "input#password")
                    pass_input.click()
                    pass_input.clear()
                    pass_input.send_keys(self.password)
                    
                    time.sleep(1)
                    login_btn = driver.find_element(By.CSS_SELECTOR, "#kc-login")
                    login_btn.click()
                    
                    self.logger.info("Credentials submitted.")
                    time.sleep(5)
                except Exception as e:
                    self.logger.error(f"Login interaction failed: {e}")
                    self.take_screenshot(driver, "zeit_login_failed")
                    return None

            # --- Check Issue Date & Navigate ---
            self.logger.info(f"Navigating to download URL: {self.download_url}")
            driver.get(self.download_url)
            time.sleep(3)
            
            current_issue_id = None
            
            # 1. Find "ZUR AKTUELLEN AUSGABE" button
            # HTML: <a href="/abo/diezeit/17.12.2025" ...>ZUR AKTUELLEN AUSGABE</a>
            
            issue_btn = None
            try:
                # Try explicit text match (case insensitive approach with translate() in xpath is verbose, using contains() is easier)
                # We look for "AKTUELLEN AUSGABE" to be safe
                issue_btn = driver.find_element(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aktuellen ausgabe')]")
            except:
                try:
                    # Fallback to class search if text fails?
                    # "btn btn-danger" might be too generic, but combined with context it could work
                    issue_btn = driver.find_element(By.CSS_SELECTOR, "a.btn-danger")
                except:
                    pass

            if issue_btn:
                try:
                    href = issue_btn.get_attribute('href')
                    self.logger.info(f"Found Issue Button pointing to: {href}")
                    # Extract date
                    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', href)
                    if match:
                        current_issue_id = match.group(1)
                        self.logger.info(f"Identified Issue Date: {current_issue_id}")
                except:
                    pass
            else:
                self.logger.warning("'ZUR AKTUELLEN AUSGABE' button not found. Checking current URL...")
                # Backup: check URL
                match = re.search(r'(\d{2}\.\d{2}\.\d{4})', driver.current_url)
                if match:
                    current_issue_id = match.group(1)
                    self.logger.info(f"Identified Issue Date from URL: {current_issue_id}")

            # --- Smart Check ---
            if current_issue_id:
                history = self.load_history()
                last_processed = history.get('last_issue_id')
                
                if last_processed == current_issue_id:
                    self.logger.info(f"Skipping: Issue {current_issue_id} already processed.")
                    return "SKIPPED"
            
            # --- Navigate to Issue Page ---
            if issue_btn and issue_btn.is_displayed():
                self.logger.info("Clicking 'ZUR AKTUELLEN AUSGABE'...")
                issue_btn.click()
                time.sleep(5)
            
            # --- Find EPUB Download ---
            # HTML: <a class="..." ...> EPUB FÜR E-READER LADEN </a>
            self.logger.info("Looking for 'EPUB FÜR E-READER LADEN'...")
            
            try:
                # 1. Specific Text Search
                # xpath contains text 'EPUB FÜR E-READER LADEN' (case insensitive match for safety)
                xpath_text = "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'epub für e-reader laden')]"
                
                epub_link = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_text)))
                self.logger.info("Found EPUB link via text. Clicking...")
                epub_link.click()
                
            except:
                self.logger.warning("Specific text link not found. Trying backup selectors...")
                try:
                    # 2. Try just "EPUB" text
                    epub_link = driver.find_element(By.XPATH, "//*[contains(text(), 'EPUB')]")
                    epub_link.click()
                except:
                    self.logger.error("Could not find EPUB link.")
                    self.take_screenshot(driver, "epub_link_missing")
                    return None
            
            # Wait for download
            self.logger.info("Waiting for download...")
            timeout = 60
            start_time = time.time()
            downloaded_file = None
            
            while time.time() - start_time < timeout:
                epubs = glob.glob(os.path.join(self.download_dir, "*.epub"))
                if epubs:
                    latest_epub = max(epubs, key=os.path.getctime)
                    if os.path.getctime(latest_epub) > start_time - 10:
                        crdownloads = glob.glob(os.path.join(self.download_dir, "*.crdownload"))
                        if not crdownloads:
                            downloaded_file = latest_epub
                            break
                time.sleep(1)
            
            if downloaded_file:
                self.logger.info(f"Download complete: {downloaded_file}")
                if current_issue_id:
                    self.save_history(current_issue_id)
                return downloaded_file
            else:
                self.logger.error("Download timed out.")
                self.take_screenshot(driver, "download_timeout")
                return None
        
        except Exception as e:
            self.logger.error(f"ZeitScraper crashed: {e}")
            if driver:
                self.take_screenshot(driver, "scraper_crash")
            return None
            
        finally:
            if driver:
                driver.quit()
