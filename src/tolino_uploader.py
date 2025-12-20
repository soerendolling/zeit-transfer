import os
import time
import logging
from playwright.sync_api import sync_playwright

class TolinoUploader:
    def __init__(self, username, password, login_url, state_file=None):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.state_file = state_file
        self.logger = logging.getLogger(__name__)

    def upload_epub(self, file_path):
        """
        Logs in to Tolino Webreader and uploads the EPUB file.
        Returns True if successful, False otherwise.
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            
            # Load state if exists
            loaded_session = False
            if self.state_file and os.path.exists(self.state_file):
                self.logger.info(f"Loading session from {self.state_file}")
                context = browser.new_context(storage_state=self.state_file)
                loaded_session = True
            else:
                context = browser.new_context()
                
            page = context.new_page()

            try:
                self.logger.info(f"Navigating to Tolino login page: {self.login_url}")
                page.goto(self.login_url)
                
                # Check if we are already logged in (redirected to library)
                already_logged_in = False
                if loaded_session:
                    try:
                        page.wait_for_url("**/library**", timeout=10000)
                        self.logger.info("Session valid. Already logged in.")
                        already_logged_in = True
                    except:
                        self.logger.info("Session invalid or expired. Proceeding to login.")

                if not already_logged_in:
                    # Handle cookie banner if present
                    try:
                        page.wait_for_selector("button:has-text('Alle akzeptieren')", timeout=5000)
                        page.click("button:has-text('Alle akzeptieren')")
                    except:
                        pass
    
                    # Wait for login button and click
                    # Usually there is an "Anmelden" button.
                    try:
                        page.click("text=Anmelden", timeout=5000)
                    except:
                        self.logger.info("'Anmelden' button not found, maybe already on login selection.")
    
                    # Select Country "Deutschland"
                    self.logger.info("Selecting country 'Deutschland'...")
                    try:
                        # Try to find Deutschland in a list or dropdown
                        # Common selectors for country selection
                        page.click("text=Deutschland", timeout=5000)
                        # Wait a moment for the provider list to update/load
                        time.sleep(2)
                    except:
                        self.logger.warning("Country 'Deutschland' not found or not clickable. Proceeding to provider selection...")
    
                    # Select "Thalia" provider
                    self.logger.info("Selecting 'Thalia' provider...")
                    thalia_selected = False
                    try:
                        # Look for text "Thalia" or image with alt "Thalia"
                        # Sometimes it is a button with an image
                        if page.is_visible("text=Thalia"):
                            page.click("text=Thalia")
                            thalia_selected = True
                        elif page.is_visible("img[alt*='Thalia']"):
                            page.click("img[alt*='Thalia']")
                            thalia_selected = True
                        else:
                            # Try searching for it if there's a search box? 
                            # Or waiting a bit more
                            page.wait_for_selector("text=Thalia", timeout=5000)
                            page.click("text=Thalia")
                            thalia_selected = True
                    except Exception as e:
                        self.logger.error(f"Could not find 'Thalia' option: {e}")
                        return False
                    
                    if not thalia_selected:
                        self.logger.error("Thalia selection failed (not found).")
                        return False
    
                    # User says: "when trieng to enter credentials ypu first have to klick the anmelden button"
                    # This implies after selecting Thalia, we might need to click "Anmelden" again on the Thalia page.
                    self.logger.info("Waiting for Thalia page and looking for 'Anmelden'...")
                    try:
                        # Wait explicitly for the Anmelden button to appear. 
                        # Use get_by_role or get_by_label as suggested by user
                        self.logger.info("Looking for 'Anmelden' button using role/label...")
                        
                        # Try finding it
                        anmelden_btn = None
                        try:
                            anmelden_btn = page.get_by_role("button", name="Anmelden").first
                            if not anmelden_btn.is_visible():
                                anmelden_btn = page.get_by_label("Anmelden").first
                        except:
                            pass
    
                        if anmelden_btn and anmelden_btn.is_visible():
                             self.logger.info("Found 'Anmelden' button. Clicking...")
                             anmelden_btn.click()
                             
                             # Wait for redirection to Thalia Auth
                             self.logger.info("Waiting for redirection to Thalia login page...")
                             try:
                                 page.wait_for_url("**/auth/oauth2/**", timeout=20000)
                             except:
                                 self.logger.warning("Redirection wait timed out, but checking for form anyway.")
                        else:
                            self.logger.warning("'Anmelden' button not found via role/label. Trying text fallback...")
                            page.click("text=Anmelden", timeout=5000)
                    except Exception as e:
                        self.logger.info(f"'Anmelden' button interaction failed: {e}")
                        self.logger.info("Assuming we might already be on the login page or direct login form.")
    
                    # Now we should be on the login form
                    self.logger.info("Entering credentials...")
                    
                    # Check if we are seeing the form
                    try:
                        # Wait for password input to be ready
                        page.wait_for_selector("input[type='password']", state="visible", timeout=20000)
                    except:
                        self.logger.error("Password input not found. Login form navigation failed.")
                        # Screenshot for debug
                        page.screenshot(path="thalia_login_fail.png")
                        self.logger.info("Saved thalia_login_fail.png")
                        return False
                    
                    # Try to fill email - check for various potential names
                    email_filled = False
                    for selector in ["input[type='email']", "input[name='email']", "input[name='username']", "input[name='id']"]:
                        if page.is_visible(selector):
                            page.fill(selector, self.username)
                            email_filled = True
                            break
                    
                    if not email_filled:
                        self.logger.warning("Could not find visible email input. Trying to force fill 'input[name=username]'.")
                        try:
                            page.fill("input[name='username']", self.username)
                        except:
                            pass
                    
                    # Try to fill password
                    page.fill("input[type='password']", self.password)
                    
                    # Click submit
                    self.logger.info("Submitting credentials...")
                    try:
                        page.click("button.element-button-primary, button:has-text('Anmelden'), button[type='submit']", timeout=10000)
                    except:
                        self.logger.error("Submit button not found.")
                        return False
                    
                    # Check for CAPTCHA/Cloudflare
                    self.logger.info("Checking for potential CAPTCHA/Cloudflare...")
                    # User says: "checkbox appears clickable 3s after page is loaded"
                    time.sleep(5) 
                    
                    try:
                        # Look for Cloudflare Turnstile
                        # Structure provided: <div class="cb-c"><label class="cb-lb"><input type="checkbox">...</label></div>
                        
                        captcha_clicked = False
                        
                        # 1. Search in frames (most likely for Cloudflare)
                        for frame in page.frames:
                            try:
                                # Try specific Cloudflare selectors
                                cf_checkbox = frame.locator("label.cb-lb input[type='checkbox']").first
                                if not cf_checkbox.is_visible():
                                    cf_checkbox = frame.locator("input[type='checkbox']").first
                                
                                if cf_checkbox.is_visible():
                                    self.logger.info(f"Found visible checkbox in frame {frame.name or 'unknown'}. Clicking...")
                                    cf_checkbox.click()
                                    captcha_clicked = True
                                    break
                            except:
                                pass
                        
                        # 2. Search in main page if not found in frames
                        if not captcha_clicked:
                            try:
                                cf_checkbox = page.locator("label.cb-lb input[type='checkbox']").first
                                if cf_checkbox.is_visible():
                                    self.logger.info("Found visible checkbox on main page. Clicking...")
                                    cf_checkbox.click()
                                    captcha_clicked = True
                            except:
                                pass
                        
                        # 3. Fallback to verifying text
                        if not captcha_clicked:
                             try:
                                 text_locator = page.get_by_text("Bestätigen Sie, dass Sie ein Mensch sind", exact=False).first
                                 if text_locator.is_visible():
                                     self.logger.info("Found CAPTCHA text. Clicking matches...")
                                     text_locator.click()
                                     captcha_clicked = True
                             except:
                                 pass
    
                        if captcha_clicked:
                            self.logger.info("CAPTCHA checkbox clicked. Waiting for verification...")
                            time.sleep(2)
    
                    except Exception as e:
                        self.logger.info(f"CAPTCHA interaction attempt failed: {e}")
    
                    # Wait for main library page
                    self.logger.info("Waiting for redirect to library...")
                    try:
                        page.wait_for_url("**/library**", timeout=60000) 
                        self.logger.info("Login successful.")
                        if self.state_file:
                            context.storage_state(path=self.state_file)
                            self.logger.info(f"Session saved to {self.state_file}")
                    except:
                        self.logger.warning("Automated login stuck. PLEASE SOLVE CAPTCHA MANUALLY IN BROWSER.")
                        # Wait longer for user to solve it
                        try:
                            page.wait_for_url("**/library**", timeout=180000) # 3 minutes extra
                            self.logger.info("Login successful after manual intervention.")
                            if self.state_file:
                                context.storage_state(path=self.state_file)
                                self.logger.info(f"Session saved to {self.state_file}")
                        except:
                            self.logger.error("Login verification timed out.")
                            page.screenshot(path="login_timeout.png")
                            return False

                # Upload file
                self.logger.info(f"Uploading {file_path}...")
                
                # In Playwright, we handle file uploads by setting the input files
                # We need to find the file input element. It might be hidden.
                # Often there is an "Upload" button that triggers a file chooser.
                
                # We look for an upload button.
                # It might be an icon with a specific aria-label or class.
                # Common aria-labels: "Upload", "Datei hochladen", "Buch hochladen"
                
                upload_button = None
                for label in ["Upload", "Datei hochladen", "Buch hochladen", "Hinzufügen"]:
                    try:
                        upload_button = page.get_by_label(label).first
                        if upload_button.is_visible():
                            break
                    except:
                        pass
                
                if not upload_button or not upload_button.is_visible():
                    # Try by icon class or similar if text fails
                    # This is tricky without inspection.
                    # Let's try a generic file input if present
                    file_input = page.locator("input[type='file']")
                    if file_input.count() > 0:
                        self.logger.info("Found hidden file input, setting files directly.")
                        file_input.set_files(file_path)
                    else:
                        # Try clicking a likely button to trigger chooser
                        # Maybe a button with a plus icon?
                        self.logger.warning("Upload button not found by label. Trying generic button search...")
                        # This is a guess.
                        return False
                else:
                    with page.expect_file_chooser() as fc_info:
                        upload_button.click()
                    
                    file_chooser = fc_info.value
                    file_chooser.set_files(file_path)
                
                # Wait for upload to complete
                # Look for a success message or the file appearing in the list
                self.logger.info("Waiting for upload to complete...")
                time.sleep(15) # Simple wait
                
                self.logger.info("Upload likely successful.")
                return True

            except Exception as e:
                self.logger.error(f"An error occurred during Tolino upload: {e}")
                try:
                    page.screenshot(path="tolino_error.png")
                    self.logger.info("Saved tolino_error.png")
                except:
                    pass
                return False
            finally:
                browser.close()
