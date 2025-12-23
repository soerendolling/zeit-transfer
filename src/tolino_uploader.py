import os
import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TolinoUploader:
    def __init__(self, username, password, login_url):
        self.username = username
        self.password = password
        self.login_url = login_url 
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
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

            driver = uc.Chrome(use_subprocess=True, options=options)
            driver.set_window_size(1920, 1080)
            
            wait = WebDriverWait(driver, 20)
            
            # --- Login Phase ---
            self.logger.info(f"Navigating to {self.login_url}")
            driver.get(self.login_url)
            
            # Detect Cloudflare Block
            page_text = driver.find_element(By.TAG_NAME, "body").text
            if "Zugriff wurde geblockt" in page_text or "Ray ID" in page_text:
                self.logger.error("ACCESS DENIED: The browser has been blocked by the site's WAF (Cloudflare).")
                self.take_screenshot(driver, "waf_blocked")
                return False

            # Smart check for login state
            # Wait for either 'Deutschland' (not logged in) OR 'Library Menu' (logged in)
            is_logged_in = False
            try:
                # Give it a moment to load
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
                # Check for indicators
                if len(driver.find_elements(By.CSS_SELECTOR, "button[data-test-id='library-headerBar-overflowMenu-button']")) > 0:
                     is_logged_in = True
                     self.logger.info("Already logged in (Menu found).")
            except:
                pass
            
            if not is_logged_in:
                self.logger.info("Performing Login Sequence...")

                # 1. Country Selection
                self.logger.info("Looking for Country Selection...")
                try:
                    # Wait explicitly
                    de_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Deutschland')]")))
                    de_btn.click()
                    self.logger.info("Clicked 'Deutschland'.")
                except:
                    self.logger.info("Country selection skipped (not found or already selected).")

                # 2. Provider "Thalia DE"
                self.logger.info("Looking for Provider 'Thalia DE'...")
                try:
                     thalia_img = wait.until(EC.element_to_be_clickable((By.XPATH, "//img[@alt='Thalia DE']")))
                     try:
                         thalia_img.click()
                     except:
                         thalia_img.find_element(By.XPATH, "./..").click()
                     self.logger.info("Clicked 'Thalia DE'.")
                except:
                     self.logger.info("Provider selection skipped.")

                # 3. Thalia Login Form
                self.logger.info("Waiting for Login Form...")
                
                # Handle 'Anmelden' landing page button if sticking
                try:
                    anmelden_landing = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Anmelden')]")))
                    if anmelden_landing.is_displayed():
                        anmelden_landing.click()
                except:
                    pass
                
                # Enter Credentials
                try:
                    # Specific wait for Thalia/Tolino user input
                    user_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username'], input[name='email'], input[type='email']")))
                    time.sleep(1) # Stabilization wait
                    user_input.click()
                    user_input.clear()
                    user_input.send_keys(self.username)
                    
                    try:
                        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    except:
                        # Sometimes need to hit enter to reveal password
                        user_input.send_keys(Keys.RETURN)
                        pass_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']")))
                    
                    pass_input.click()
                    pass_input.clear()
                    pass_input.send_keys(self.password)
                    pass_input.send_keys(Keys.RETURN)
                    self.logger.info("Credentials submitted.")
                    
                    # 4. Verify Success
                    self.logger.info("Waiting for successful login redirect...")
                    
                    # Wait for library URL AND absence of Anmelden button
                    wait.until(EC.url_contains("library"))
                    
                    # Ensure 'Anmelden' is gone (give it a few seconds to transition)
                    WebDriverWait(driver, 15).until_not(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Anmelden')]"))
                    )
                    self.logger.info("Login verified.")
                    
                except Exception as e:
                    self.logger.error(f"Login Failure: {e}")
                    self.take_screenshot(driver, "login_failed")
                    return False

            # --- Navigation Phase ---
            target_url = "https://webreader.mytolino.com/library/index.html#/mybooks/titles"
            self.logger.info(f"Navigating to specific upload page: {target_url}")
            driver.get(target_url)
            
            # Wait for Overflow Menu button
            self.logger.info("Waiting for page header/menu to load...")
            try:
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
                # Wait a tiny bit for UI to settle before closing (optional safety)
                time.sleep(1) 
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
