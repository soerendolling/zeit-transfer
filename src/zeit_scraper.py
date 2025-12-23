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
    def __init__(self, username, password, login_url, download_url, download_dir="temp", history_file="download_history.json", test_mode=False):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.download_url = download_url
        self.download_dir = os.path.abspath(download_dir)
        self.history_file = history_file
        self.test_mode = test_mode
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
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
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
            driver.set_window_size(1920, 1080)
            
            wait = WebDriverWait(driver, 20)
            
            # --- Login Phase ---
            self.logger.info(f"Navigating to login page: {self.login_url}")
            driver.get(self.login_url)
            # Remove static sleep, wait for username or active session indicator

            # Detect Login State
            needs_login = False
            try:
                # Wait up to 5s for either username OR logout button
                login_or_account = WebDriverWait(driver, 5).until(
                   EC.presence_of_element_located((By.XPATH, "//*[@id='username'] | //*[contains(text(), 'Abmelden')] | //*[contains(text(), 'Konto')]"))
                )
                
                # Check what we found
                if login_or_account.get_attribute("id") == "username":
                     needs_login = True
                     self.logger.info("Login form detected.")
                else:
                     self.logger.info("Active session detected.")
                     needs_login = False
            except:
                # Fallback
                self.logger.info("Login state unclear, assuming login needed.")
                needs_login = True

            if needs_login:
                try:
                    cookie_btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='Zustimmen']")))
                    cookie_btn.click()
                except:
                    pass
                
                try:
                    self.logger.info("Entering credentials...");
                    email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input#username")))
                    time.sleep(1) # Focus wait
                    email_input.click()
                    email_input.clear()
                    email_input.send_keys(self.username)
                    
                    pass_input = driver.find_element(By.CSS_SELECTOR, "input#password")
                    pass_input.click()
                    pass_input.clear()
                    pass_input.send_keys(self.password)
                    
                    # Submit
                    login_btn = driver.find_element(By.CSS_SELECTOR, "#kc-login")
                    login_btn.click()
                    self.logger.info("Credentials submitted.")

                    # Wait for redirect or change in UI
                    # We wait for either the login button to be gone OR the URL to change
                    WebDriverWait(driver, 20).until(
                        lambda d: d.current_url != self.login_url or \
                                 len(d.find_elements(By.CSS_SELECTOR, "#kc-login")) == 0 or \
                                 len(d.find_elements(By.XPATH, "//*[contains(text(), 'Abmelden')]")) > 0
                    )
                    self.logger.info("Login successful (detected via UI change).")
                except Exception as e:
                    self.logger.error(f"Login interaction failed: {e}")
                    self.logger.info(f"Current URL: {driver.current_url}")
                    self.take_screenshot(driver, "zeit_login_failed")
                    return None

            # --- Check Issue Date & Navigate ---
            self.logger.info(f"Navigating to download URL: {self.download_url}")
            driver.get(self.download_url)
            
            current_issue_id = None
            
            # 1. Wait for ANY key element to be present (button or title) to ensure page load
            try:
                # Look for "Aktuelle Ausgabe" or just generic body check
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except:
                pass

            # 1. Find "ZUR AKTUELLEN AUSGABE" button
            issue_btn = None
            try:
                # Try explicit text match
                issue_btn = driver.find_element(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aktuellen ausgabe')]")
            except:
                try:
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
                
                if self.test_mode:
                    self.logger.info(f"Test Mode: Ignoring history check (Issue {current_issue_id} vs Last {last_processed})")
                elif last_processed == current_issue_id:
                    self.logger.info(f"Skipping: Issue {current_issue_id} already processed.")
                    return "SKIPPED"
            
            # --- Navigate to Issue Page ---
            if issue_btn and issue_btn.is_displayed():
                self.logger.info("Clicking 'ZUR AKTUELLEN AUSGABE'...")
                issue_btn.click()
            
            # --- Find EPUB Download ---
            self.logger.info("Looking for 'EPUB FÜR E-READER LADEN'...")
            
            try:
                # 1. Simple Text Search "EPUB" (Fastest)
                xpath_text = "//*[contains(text(), 'EPUB')]"
                
                epub_link = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_text)))
                self.logger.info("Found EPUB link via text. Clicking...")
                epub_link.click()
                
            except:
                self.logger.warning("Simple 'EPUB' text link not found. Trying specific text...")
                try:
                    # 2. Specific Backup if "EPUB" is too generic (unlikely)
                    xpath_text = "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'epub für e-reader laden')]"
                    epub_link = driver.find_element(By.XPATH, xpath_text)
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
                time.sleep(0.5) # reduced check interval
            
            if downloaded_file:
                self.logger.info(f"Download complete: {downloaded_file}")
                if current_issue_id and not self.test_mode:
                    self.save_history(current_issue_id)
                elif self.test_mode:
                    self.logger.info("Test Mode: Not updating history file.")
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
