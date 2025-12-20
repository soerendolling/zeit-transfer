import os
import time
import json
import logging
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Undetected Chromedriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

class TolinoApiClient:
    # Credentials from public documentation (Tolino Vision / Thalia App)
    CLIENT_ID = "treaderapp01"
    CLIENT_SECRET = "GPvCYjsNqZJkQsyZ9VUF"
    
    AUTH_URL = "https://thalia.de/auth/oauth2/authorize"
    TOKEN_URL = "https://thalia.de/auth/oauth2/token"
    # Endpoints found in docs
    UPLOAD_URL = "https://bosh.pageplace.de/bosh/rest/upload"
    
    # Redirect URI used by the app
    REDIRECT_URI = "epublishing://login" 
    
    def __init__(self, token_file="tolino_token.json"):
        self.token_file = token_file
        self.logger = logging.getLogger(__name__)
        self.access_token = None
        self.refresh_token = None
        
        self.load_tokens()

    def load_tokens(self):
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.refresh_token = data.get("refresh_token")
                    self.logger.info(f"Loaded refresh token from {self.token_file}")
            except Exception as e:
                self.logger.error(f"Failed to load tokens: {e}")

    def save_tokens(self, token_data):
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            self.logger.info(f"Tokens saved to {self.token_file}")
            
            self.refresh_token = token_data.get("refresh_token")
            self.access_token = token_data.get("access_token")
        except Exception as e:
            self.logger.error(f"Failed to save tokens: {e}")

    def login(self):
        """
        Interactively logs in via Undetected Chromedriver to capture the authorization code.
        Bypasses Cloudflare loops better than standard Selenium.
        """
        self.logger.info("Starting interactive login with Undetected Chromedriver...")
        
        # Initialize Driver
        try:
            # use_subprocess=True is often more stable on Mac
            options = uc.ChromeOptions()
            # Mimic the Tolino eReader User Agent
            options.add_argument('--user-agent=DT_EINK_10_NETRONIX DT_EINK_UPD_PP_14.1.0')
            options.add_argument('--window-size=1024,768')
            
            driver = uc.Chrome(use_subprocess=True, options=options)
        except Exception as e:
            self.logger.error(f"Failed to initialize Undetected ChromeDriver: {e}")
            return False

        try:
            # Construct Auth URL
            scope = "SCOPE_BOSH SCOPE_BUCHDE SCOPE_MANDANT_ID.2004 SCOPE_LOGIN FAMILY"
            params = {
                "response_type": "code",
                "scope": scope,
                "redirect_uri": self.REDIRECT_URI,
                "client_id": self.CLIENT_ID,
                "x_buchde.skin_id": "17" # Thalia Skin ID
            }
            
            # Build full URL manually
            auth_url_full = requests.Request('GET', self.AUTH_URL, params=params).prepare().url
            self.logger.info(f"Opening Auth URL: {auth_url_full}")
            
            driver.get(auth_url_full)
            self.logger.info("Automation: Attempting partial form fill...")

            # --- Automation Block ---
            try:
                username = os.getenv("TOLINO_USER")
                password = os.getenv("TOLINO_PASSWORD")
                
                if username and password:
                    # Wait for input fields
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='email' or @name='username' or @name='id']"))
                    )
                    
                    # Fill Username if empty
                    user_input = driver.find_element(By.XPATH, "//input[@type='email' or @name='username' or @name='id']")
                    user_input.click() 
                    user_input.clear()
                    user_input.send_keys(username)
                    self.logger.info("Filled username.")
                    
                    # Some flows have password on next screen or same
                    try:
                        password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                        password_input.click()
                        password_input.clear()
                        password_input.send_keys(password)
                        self.logger.info("Filled password.")
                        
                        # Submit
                        password_input.send_keys(Keys.RETURN)
                        self.logger.info("Sent RETURN key.")
                        
                    except:
                        self.logger.info("Password input not immediately found (maybe multi-step login).")
                     
                else:
                    self.logger.warning("No credentials found in .env for automation.")
                    
            except Exception as auto_e:
                 self.logger.warning(f"Automation step failed (falling back to manual): {auto_e}")
            # ------------------------

            self.logger.info("Please complete log in manually in the browser window if needed...")
            
            auth_code = None
            
            # Polling loop to check URL
            start_time = time.time()
            while time.time() - start_time < 300: # 5 minutes timeout
                try:
                    current_url = driver.current_url
                    
                    # Check for code in URL
                    if "code=" in current_url:
                        # Check if it is the specific redirect or just contains the code parameter
                        # We are lenient here because exact URL matching can be flaky during redirect
                        self.logger.info(f"Detected potential Redirect URL: {current_url}")
                        parsed = urlparse(current_url)
                        qs = parse_qs(parsed.query)
                        if 'code' in qs:
                            auth_code = qs['code'][0]
                            self.logger.info(f"CAPTURED AUTH CODE: {auth_code}")
                            break
                            
                except Exception as e:
                    # Driver might disconnect or be busy
                    pass
                
                time.sleep(0.5)
                
            if auth_code:
                try:
                    driver.quit()
                except:
                    pass
                return self.exchange_code_for_token(auth_code)
            else:
                self.logger.error("Login timed out or failed to capture code.")
                try:
                    driver.quit()
                except:
                    pass
                return False

        except Exception as e:
            self.logger.error(f"Login process failed: {e}")
            try:
                driver.quit()
            except:
                pass
            return False

    def exchange_code_for_token(self, code):
        self.logger.info("Exchanging code for tokens...")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.REDIRECT_URI,
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.save_tokens(token_data)
            return True
        except Exception as e:
            self.logger.error(f"Token exchange failed: {e}")
            if 'response' in locals() and response:
                 self.logger.error(f"Response: {response.text}")
            return False

    def refresh_access_token(self):
        if not self.refresh_token:
            self.logger.error("No refresh token available.")
            return False
            
        self.logger.info("Refreshing access token...")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            if "refresh_token" not in token_data:
                token_data["refresh_token"] = self.refresh_token
                
            self.save_tokens(token_data)
            return True
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            if hasattr(e, 'response') and e.response:
                 self.logger.error(f"Response: {e.response.text}")
            return False

    def upload(self, file_path):
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False
            
        if not self.refresh_token:
            self.logger.warning("No refresh token found. Initiating interactive login...")
            if not self.login():
                return False

        if not self.refresh_access_token():
            self.logger.warning("Token refresh failed. Trying complete re-login...")
            if not self.login():
                return False
                
        self.logger.info(f"Uploading file via API: {file_path}")
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        control_data = {
            "filesize": file_size,
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        
        files = {
            'control': (None, json.dumps(control_data), 'application/json'),
            'file': (filename, open(file_path, 'rb'), 'application/epub+zip')
        }
        
        try:
            response = requests.post(self.UPLOAD_URL, headers=headers, files=files)
            files['file'][1].close()
            
            if response.status_code in [200, 201]:
                self.logger.info("API Upload successful!")
                self.logger.info(f"Response: {response.text}")
                return True
            else:
                self.logger.error(f"API Upload failed: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
             self.logger.error(f"API Request failed: {e}")
             return False
