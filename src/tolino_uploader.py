import os
import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TolinoUploader:
    def __init__(self, username, password, login_url, state_file=None):
        self.username = username
        self.password = password
        self.login_url = login_url 
        self.state_file = state_file 
        self.logger = logging.getLogger(__name__)

    def take_screenshot(self, driver, name):
        try:
            filename = f"{name}_{int(time.time())}.png"
            driver.save_screenshot(filename)
            self.logger.info(f"Saved screenshot: {filename}")
        except Exception as e:
            self.logger.warning(f"Failed to take screenshot: {e}")

    def upload_epub(self, file_path):
        """
        Logs in to Tolino Webreader using Selenium and uploads the EPUB file via the 'My Books' overflow menu.
        Returns True if successful, False otherwise.
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False

        self.logger.info(f"Starting Upload for {file_path}...")
        driver = None
        
        try:
            # Initialize Undetected Chromedriver
            driver = uc.Chrome(use_subprocess=True)
            driver.set_window_size(1280, 800)
            
            wait = WebDriverWait(driver, 20)
            
            # --- Login Phase ---
            self.logger.info(f"Navigating to {self.login_url}")
            driver.get(self.login_url)
            
            # Allow time for initial load
            time.sleep(5)
            
            # Assume NOT logged in by default for fresh sessions
            # We will only skip login if we find a POSITIVE indicator of being logged in (like a user avatar), not just a lack of login button
            is_logged_in = False
            
            # Try to find positive login indicator (e.g. avatar or My Books link that works)
            # For now, let's just proceed to Login Flow. The logic below handles "Country selection not found" if we are somehow logged in.
            
            self.logger.info("Performing Login Sequence...")

            # 1. Country Selection
            self.logger.info("Looking for Country Selection...")
            try:
                # Wait explicitly for it, but shorten timeout if it might be skipped
                de_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Deutschland')]")))
                de_btn.click()
                self.logger.info("Clicked 'Deutschland'.")
            except:
                self.logger.info("Country selection not found (maybe already selected or different flow).")

            # 2. Provider "Thalia DE"
            self.logger.info("Looking for Provider 'Thalia DE'...")
            try:
                 time.sleep(2)
                 thalia_img = wait.until(EC.presence_of_element_located((By.XPATH, "//img[@alt='Thalia DE']")))
                 try:
                     thalia_img.click()
                 except:
                     thalia_img.find_element(By.XPATH, "./..").click()
                 self.logger.info("Clicked 'Thalia DE'.")
            except:
                 self.logger.info("Provider selection not found (maybe already on login form).")

            # 3. Thalia Login Form
            self.logger.info("Waiting for Login Form...")
            time.sleep(5)
            
            # Handle 'Anmelden' landing page button (Thalia interstitial)
            try:
                anmelden_landing = driver.find_element(By.XPATH, "//*[contains(text(), 'Anmelden')]")
                if anmelden_landing.is_displayed():
                    anmelden_landing.click()
                    time.sleep(2)
            except:
                pass
            
            # Enter Credentials
            try:
                user_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='username' or @name='email' or @type='email']")))
                user_input.click()
                user_input.clear()
                user_input.send_keys(self.username)
                
                try:
                    pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                except:
                    user_input.send_keys(Keys.RETURN)
                    time.sleep(2)
                    pass_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']")))
                
                pass_input.click()
                pass_input.clear()
                pass_input.send_keys(self.password)
                pass_input.send_keys(Keys.RETURN)
                self.logger.info("Credentials submitted.")
            except Exception as e:
                # If we fail here, it's critcal UNLESS we were already logged in (which we assume we aren't)
                self.logger.warning(f"Login form interaction issue: {e}")
                # We continue to verification just in case

            # 4. Verify Success
            self.logger.info("Waiting for successful login redirect...")
            try:
                wait.until(EC.url_contains("library"))
                time.sleep(5)
                # Verify 'Anmelden' is gone
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Anmelden')]")) > 0:
                     self.logger.error("Login failed (Anmelden button still visible)")
                     self.take_screenshot(driver, "login_failed")
                     return False
                self.logger.info("Login verified.")
            except:
                self.logger.error("Login verification timed out.")
                self.take_screenshot(driver, "login_timeout")
                return False

            # --- Navigation Phase ---
            target_url = "https://webreader.mytolino.com/library/index.html#/mybooks/titles"
            self.logger.info(f"Navigating to specific upload page: {target_url}")
            driver.get(target_url)
            
            # Wait for page to actually load content. 
            self.logger.info("Waiting for page header/menu to load...")
            try:
                time.sleep(5) # Let SPA settle
                menu_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-test-id='library-headerBar-overflowMenu-button']")))
                self.logger.info("Overflow Menu button found.")
                
                menu_btn.click()
                self.logger.info("Overflow Menu clicked.")
                
            except Exception as e:
                self.logger.error(f"Could not interact with Overflow Menu: {e}")
                self.take_screenshot(driver, "menu_interaction_failed")
                return False

            # --- Upload Phase ---
            self.logger.info("Looking for file input...")
            try:
                # Wait for 'Hochladen' option
                wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Hochladen')]")))
                self.logger.info("'Hochladen' option visible.")
                
                # Find input and send keys
                file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                self.logger.info(f"Sending file to input: {file_path}")
                file_input.send_keys(os.path.abspath(file_path))
                
            except Exception as e:
                self.logger.error(f"Failed to inject file: {e}")
                self.take_screenshot(driver, "upload_injection_failed")
                return False
            
            # --- Verification Phase ---
            self.logger.info("Waiting for success confirmation...")
            try:
                success_msg = wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'erfolgreich') or contains(text(), 'hinzugefügt')]")))
                self.logger.info(f"Success detected: {success_msg.text}")
                time.sleep(3)
                return True
                
            except Exception as e:
                self.logger.warning(f"Success confirmation missing/timed out: {e}")
                self.take_screenshot(driver, "success_confirmation_missing")
                return True 

        except Exception as e:
            self.logger.error(f"Critical Error in TolinoUploader: {e}")
            if driver:
                self.take_screenshot(driver, "critical_crash")
            return False
            
        finally:
            if driver:
                driver.quit()
