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
        self.login_url = login_url # usually https://webreader.mytolino.com/library/index.html#/
        self.state_file = state_file # Not strictly used with UC in this simple implementation, but kept for interface compat
        self.logger = logging.getLogger(__name__)

    def upload_epub(self, file_path):
        """
        Logs in to Tolino Webreader using Selenium and uploads the EPUB file.
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
            
            # Navigate
            self.logger.info(f"Navigating to {self.login_url}")
            driver.get(self.login_url)
            
            wait = WebDriverWait(driver, 20)
            
            # --- Login Flow ---
            
            # Check if we need to login (Country selection visible?)
            # or if we are already logged in (Library visible?)
            
            time.sleep(5)
            if "library" in driver.current_url and len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Anmelden')]")) == 0:
                 self.logger.info("Already logged in.")
            else:
                self.logger.info("Performing Login...")
                
                # 1. Select Country "Deutschland"
                try:
                    de_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Deutschland')]")))
                    de_btn.click()
                    self.logger.info("Clicked 'Deutschland'.")
                except:
                    self.logger.info("Country selection not found (maybe skipped).")

                # 2. Select Provider "Thalia DE"
                try:
                     time.sleep(2)
                     # Use the selector verified in test_selenium_login.py
                     thalia_img = wait.until(EC.presence_of_element_located((By.XPATH, "//img[@alt='Thalia DE']")))
                     try:
                         thalia_img.click()
                     except:
                         thalia_img.find_element(By.XPATH, "./..").click()
                     self.logger.info("Clicked 'Thalia DE'.")
                except Exception as e:
                     self.logger.warning(f"Provider selection issue (maybe skipped): {e}")

                # 3. Thalia Login Form
                self.logger.info("Waiting for Login Form...")
                time.sleep(5)
                
                # Handle potential "Anmelden" landing button
                try:
                    anmelden_landing = driver.find_element(By.XPATH, "//*[contains(text(), 'Anmelden')]")
                    if anmelden_landing.is_displayed():
                        anmelden_landing.click()
                        time.sleep(2)
                except:
                    pass
                
                # Fill Credentials
                try:
                    user_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='username' or @name='email' or @type='email']")))
                    user_input.click()
                    user_input.clear()
                    user_input.send_keys(self.username)
                    
                    # Password
                    try:
                        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    except:
                        user_input.send_keys(Keys.RETURN)
                        time.sleep(2)
                        pass_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']")))
                    
                    pass_input.click()
                    pass_input.clear()
                    pass_input.send_keys(self.password)
                    
                    # Submit
                    pass_input.send_keys(Keys.RETURN)
                    self.logger.info("Credentials submitted.")
                    
                except Exception as e:
                    self.logger.error(f"Login form interaction failed: {e}")
                    # return False # Don't return yet, maybe we interpret 'already logged in' incorrectly?
            
            # 4. Wait for Library
            self.logger.info("Waiting for Library...")
            try:
                # Wait for URL and absence of 'Anmelden'
                wait.until(EC.url_contains("library"))
                time.sleep(5)
                # Verify not on login page
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Anmelden')]")) > 0:
                     self.logger.error("Login failed (Anmelden button still visible).")
                     return False
                self.logger.info("Login successful.")
            except Exception as e:
                self.logger.error("Timed out waiting for Library load.")
                return False

            # --- Upload Flow ---
            self.logger.info(f"Uploading file: {file_path}")
            
            # Tolino Webreader usually has a floating action button or menu for upload.
            # But the most reliable way with Selenium is to find the hidden input[type='file'] and send keys.
            
            try:
                # Often the input is present but hidden
                file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                
                # If it's not interactable via standard send_keys because it's hidden, 
                # we might need to make it visible via JS or use a specific Selenium trick (send_keys usually works on hidden inputs too in some drivers, but standard is it must be Interactable)
                # If it fails, we execute JS to show it.
                
                driver.execute_script("arguments[0].style.display = 'block';", file_input)
                file_input.send_keys(os.path.abspath(file_path))
                self.logger.info("Sent file to input.")
                
                # Wait for upload progress/completion
                # This depends on UI. Usually a progress bar or a toast.
                time.sleep(5)
                
                # Check for error toasts?
                # Check for success indicators? 
                # For now, we assume if no error appears, it's good.
                
                # Wait a reasonable amount for upload
                file_size_mb = os.path.getsize(file_path) / (1024*1024)
                wait_time = max(10, int(file_size_mb * 5)) # 5s per MB, min 10s
                self.logger.info(f"Waiting {wait_time}s for upload processing...")
                time.sleep(wait_time)
                
                self.logger.info("Upload sequence completed.")
                return True

            except Exception as e:
                self.logger.error(f"Upload failed: {e}")
                # Try to find an upload button to click first?
                return False

        except Exception as e:
            self.logger.error(f"TolinoUploader crashed: {e}")
            return False
            
        finally:
            if driver:
                driver.quit()
