import os
import time
import logging
from dotenv import load_dotenv

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SeleniumLoginTest")

load_dotenv()

def take_screenshot(driver, name):
    try:
        driver.save_screenshot(f"{name}.png")
        logger.info(f"Screenshot saved: {name}.png")
    except:
        pass

def test_login():
    username = os.getenv("TOLINO_USER")
    password = os.getenv("TOLINO_PASSWORD")
    
    if not username or not password:
        logger.error("Credentials not found in .env")
        return

    logger.info("Starting Selenium Webreader Login Test (v2)...")
    
    driver = None
    try:
        driver = uc.Chrome(use_subprocess=True)
        driver.set_window_size(1280, 800)
    except Exception as e:
        logger.error(f"Failed to start driver: {e}")
        return

    try:
        url = "https://webreader.mytolino.com/library/index.html#/"
        logger.info(f"Navigating to {url}")
        driver.get(url)
        
        wait = WebDriverWait(driver, 20)
        
        # 1. Select Country "Deutschland"
        logger.info("Looking for Country selection...")
        try:
            # Wait a bit for overlay
            time.sleep(3)
            take_screenshot(driver, "1_country_check")
            
            de_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Deutschland')]")))
            de_btn.click()
            logger.info("Clicked 'Deutschland'.")
        except Exception as e:
            logger.warning(f"Country selection verification: {e}")
            take_screenshot(driver, "1_country_fail")

        # 2. Select Provider "Thalia DE"
        logger.info("Looking for Provider 'Thalia DE'...")
        try:
             time.sleep(2)
             take_screenshot(driver, "2_provider_check")
             
             # User specified "Thalia DE" is the alt text
             # Try finding the image and clicking it (or its parent)
             thalia_img = wait.until(EC.presence_of_element_located((By.XPATH, "//img[@alt='Thalia DE']")))
             
             # Try clicking the image directly
             try:
                 thalia_img.click()
             except:
                 # Try clicking parent
                 thalia_img.find_element(By.XPATH, "./..").click()
                 
             logger.info("Clicked 'Thalia DE'.")
        except Exception as e:
             logger.error(f"Provider 'Thalia DE' not found: {e}")
             take_screenshot(driver, "2_provider_fail")
             # We can't proceed really if this fails
             return
        
        # 3. Handle Redirect / Login Form
        logger.info("Waiting for Login Form (Thalia)...")
        time.sleep(5) # Give it time to redirect
        take_screenshot(driver, "3_login_form_check")
        
        try:
            # Check if we need to click "Anmelden" on Thalia page first
            # Sometimes there is a landing page
            try:
                anmelden_landing = driver.find_element(By.XPATH, "//*[contains(text(), 'Anmelden')]")
                if anmelden_landing.is_displayed():
                    logger.info("Found 'Anmelden' on landing page, clicking...")
                    anmelden_landing.click()
                    time.sleep(2)
            except:
                pass

            # Look for username input
            # Thalia uses name="username" usually
            user_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='username' or @name='email' or @type='email']")))
            logger.info("Found username input.")
            
            user_input.click()
            user_input.clear()
            user_input.send_keys(username)
            
            # Password
            # Sometimes on same page, often password field is present
            try:
                pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            except:
                logger.info("Password not found immediately, checking if we need to submit username first.")
                user_input.send_keys(Keys.RETURN)
                time.sleep(2)
                pass_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']")))
            
            pass_input.click()
            pass_input.clear()
            pass_input.send_keys(password)
            logger.info("Filled credentials.")
            
            # Submit
            pass_input.send_keys(Keys.RETURN)
            logger.info("Submitted form.")
            
            # Solve CAPTCHA if automated?
            # Selenium can't easily fail here, it will just wait.
            # We assume user might help or undetected-chromedriver passes.
            
        except Exception as e:
            logger.error(f"Login form interaction failed: {e}")
            take_screenshot(driver, "3_login_fail")
            return
            
        # 5. Verify Login
        logger.info("Waiting for successful login...")
        # Success means we are NOT on the login page, and we see something internal.
        # "Mein Konto", "Meine Bücher", "Bibliothek"
        
        try:
            # Wait for URL to be back to library BUT ensure we are logged in
            # We can check if "Anmelden" is GONE
            time.sleep(5)
            wait.until(EC.url_contains("library"))
            
            # Check for success indicators
            take_screenshot(driver, "4_success_check")
            
            # If "Anmelden" is visible, we failed.
            if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Anmelden')]")) > 0:
                 logger.warning("Found 'Anmelden' button - Login might have failed?")
            else:
                 logger.info("No 'Anmelden' button found. Assuming success.")
            
            logger.info("Test Finished. Check screenshots if unsure.")
            
        except Exception as e:
            logger.error(f"Verification Failed: {e}")
            take_screenshot(driver, "4_verification_fail")
            
        # Keep browser open for user to see
        logger.info("Keeping browser open for 30s...")
        time.sleep(30)
        
    except Exception as e:
        logger.error(f"Test crashed: {e}")
        take_screenshot(driver, "crash")
        
    finally:
        if driver:
            logger.info("Closing driver.")
            driver.quit()

if __name__ == "__main__":
    test_login()
