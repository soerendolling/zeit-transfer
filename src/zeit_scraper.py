import os
import time
import logging
import glob
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ZeitScraper:
    def __init__(self, username, password, login_url, download_url, download_dir="temp", state_file=None):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.download_url = download_url
        self.download_dir = os.path.abspath(download_dir)
        self.state_file = state_file # Not strictly used in this simple Selenium version, but kept for signature compatibility
        self.logger = logging.getLogger(__name__)

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def download_latest_issue(self):
        """
        Logs in to Die Zeit and downloads the latest EPUB issue using Selenium.
        Returns the path to the downloaded file or None if failed.
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
                "plugins.always_open_pdf_externally": True # Good practice
            }
            options.add_experimental_option("prefs", prefs)
            
            # Initialize Driver
            driver = uc.Chrome(use_subprocess=True, options=options)
            driver.set_window_size(1280, 800)
            
            wait = WebDriverWait(driver, 20)
            
            # --- Login ---
            self.logger.info(f"Navigating to login page: {self.login_url}")
            driver.get(self.login_url)
            
            # Check if already logged in (redirected to account page)
            time.sleep(3)
            if "konto" in driver.current_url or "meine-inhalte" in driver.current_url:
                self.logger.info("Already logged in.")
            else:
                # Handle Cookie Banner
                try:
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='Zustimmen']")))
                    cookie_btn.click()
                    self.logger.info("Accepted cookies.")
                except:
                    pass
                
                # Perform Login
                try:
                    self.logger.info("Entering credentials...")
                    # Email
                    email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input#username")))
                    email_input.click()
                    email_input.clear()
                    email_input.send_keys(self.username)
                    
                    # Password
                    pass_input = driver.find_element(By.CSS_SELECTOR, "input#password")
                    pass_input.click()
                    pass_input.clear()
                    pass_input.send_keys(self.password)
                    
                    # Submit
                    # Sometimes nice to wait a split second
                    time.sleep(1)
                    login_btn = driver.find_element(By.CSS_SELECTOR, "#kc-login")
                    login_btn.click()
                    
                    self.logger.info("Credentials submitted.")
                    
                    # Wait for redirect
                    # success usually lands on account page or back to referer
                    time.sleep(5)
                    
                except Exception as e:
                    self.logger.error(f"Login interaction failed: {e}")
                    # Capture screenshot?
                    return None

            # --- Download ---
            self.logger.info(f"Navigating to download URL: {self.download_url}")
            driver.get(self.download_url)
            
            # "Aktuelle Ausgabe" handling
            # If we are on the subscription page, we might need to click "Zur aktuellen Ausgabe"
            try:
                # Look for a link text that says "Zur aktuellen Ausgabe"
                # Using exact text or partial
                try:
                    issue_link = driver.find_element(By.XPATH, "//a[contains(text(), 'Zur aktuellen Ausgabe')]")
                    if issue_link.is_displayed():
                        self.logger.info("Found 'Zur aktuellen Ausgabe' link. Clicking...")
                        issue_link.click()
                        time.sleep(3)
                except:
                    pass # Maybe we are already on the right page
                
                # Look for EPUB download
                # Usually text "EPUB"
                # OR a generic download button that opens a menu
                
                self.logger.info("Looking for EPUB link...")
                
                # 1. Try generic "EPUB" text
                try:
                    epub_link = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'EPUB')]")))
                    # It might be not clickable if inside a menu?
                    if not epub_link.is_displayed():
                         # Try finding "Download" menu
                         download_menu = driver.find_element(By.XPATH, "//*[contains(text(), 'Download')]")
                         download_menu.click()
                         # Wait for menu
                         time.sleep(1)
                         epub_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'EPUB')]")))
                    
                    self.logger.info("Clicking EPUB link...")
                    epub_link.click()
                    
                except Exception as e:
                    self.logger.error(f"Could not find valid EPUB link: {e}")
                    return None
                
                # Wait for download to finish
                self.logger.info("Waiting for download...")
                
                # Verification loop: check for new files in download_dir
                # We can check for .crdownload or .part files to know it's in progress
                # And wait until .epub appears
                
                timeout = 60
                start_time = time.time()
                downloaded_file = None
                
                while time.time() - start_time < timeout:
                    # Check for .epub files modified recently
                    epubs = glob.glob(os.path.join(self.download_dir, "*.epub"))
                    if epubs:
                        # Find the most recent one
                        latest_epub = max(epubs, key=os.path.getctime)
                        # Check if it was created just now (within last minute)
                        if os.path.getctime(latest_epub) > start_time - 10:
                            # Verify no .crdownload part file for it exists
                            # (Chrome uses .crdownload)
                            crdownloads = glob.glob(os.path.join(self.download_dir, "*.crdownload"))
                            if not crdownloads:
                                downloaded_file = latest_epub
                                break
                    time.sleep(1)
                
                if downloaded_file:
                    self.logger.info(f"Download complete: {downloaded_file}")
                    return downloaded_file
                else:
                    self.logger.error("Download timed out or file not found.")
                    return None

            except Exception as e:
                self.logger.error(f"Download flow failed: {e}")
                return None
        
        except Exception as e:
            self.logger.error(f"ZeitScraper crashed: {e}")
            return None
            
        finally:
            if driver:
                driver.quit()
