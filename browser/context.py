import yaml
import json
from pathlib import Path
import logging
import threading
import time
import atexit
# Use sync_api for synchronous execution as initially requested
from playwright.sync_api import sync_playwright, Playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
# Keep async imports for the example usage block if needed, or remove if sticking purely to sync
from playwright.async_api import async_playwright
import asyncio
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define root path relative to this file
# Assuming this file is in linkedin_auto_apply/browser/
ROOT_PATH = Path(__file__).parent.parent.parent

class CookieManager:
    """Enhanced cookie management with dynamic saving capabilities."""
    
    def __init__(self, context: BrowserContext, cookie_path: Path, save_interval: int = 120):
        """
        Initialize the cookie manager.
        
        Args:
            context: Browser context to manage
            cookie_path: Path to save cookies
            save_interval: Interval in seconds between automatic saves (default 2 minutes)
        """
        self.context = context
        self.cookie_path = cookie_path
        self.save_interval = save_interval
        self._stop_periodic_save = threading.Event()
        self._periodic_thread = None
        self._last_save_time = time.time()
        self._save_lock = threading.Lock()
        
        # Register cleanup on exit
        atexit.register(self.save_cookies_on_exit)
        
        # Start periodic saving
        self.start_periodic_save()
    
    def save_cookies(self, force: bool = False) -> bool:
        """
        Save cookies to file with thread safety.
        
        Args:
            force: Force save even if recently saved
            
        Returns:
            bool: True if cookies were saved, False otherwise
        """
        current_time = time.time()
        
        # Don't save too frequently unless forced
        if not force and (current_time - self._last_save_time) < 30:  # Min 30 seconds between saves
            return False
            
        with self._save_lock:
            try:
                # Ensure directory exists
                self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save storage state
                self.context.storage_state(path=str(self.cookie_path))
                self._last_save_time = current_time
                
                logger.debug(f"Cookies saved successfully to {self.cookie_path}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save cookies: {e}")
                return False
    
    def start_periodic_save(self):
        """Start the periodic cookie saving thread."""
        if self._periodic_thread and self._periodic_thread.is_alive():
            return
            
        self._stop_periodic_save.clear()
        self._periodic_thread = threading.Thread(target=self._periodic_save_worker, daemon=True)
        self._periodic_thread.start()
        logger.info(f"Started periodic cookie saving every {self.save_interval} seconds")
    
    def stop_periodic_save(self):
        """Stop the periodic cookie saving thread."""
        if self._periodic_thread and self._periodic_thread.is_alive():
            self._stop_periodic_save.set()
            self._periodic_thread.join(timeout=5)
            logger.info("Stopped periodic cookie saving")
    
    def _periodic_save_worker(self):
        """Worker thread for periodic cookie saving."""
        while not self._stop_periodic_save.wait(self.save_interval):
            try:
                # Check if context is still valid
                if self.context and not self.context.browser.is_connected():
                    logger.debug("Browser context disconnected, stopping periodic saves")
                    break
                    
                self.save_cookies()
                
            except Exception as e:
                logger.error(f"Error in periodic cookie save: {e}")
    
    def save_cookies_on_exit(self):
        """Save cookies on application exit."""
        try:
            self.stop_periodic_save()
            if self.context and self.context.browser.is_connected():
                self.save_cookies(force=True)
                logger.info("Saved cookies on application exit")
        except Exception as e:
            logger.error(f"Error saving cookies on exit: {e}")

# Global cookie manager instance
_cookie_manager = None

def get_cookie_manager() -> CookieManager:
    """Get the global cookie manager instance."""
    global _cookie_manager
    return _cookie_manager

def set_cookie_manager(manager: CookieManager):
    """Set the global cookie manager instance."""
    global _cookie_manager
    _cookie_manager = manager

def save_cookies_now(force: bool = False) -> bool:
    """
    Manually save cookies using the global cookie manager.
    
    Args:
        force: Force save even if recently saved
        
    Returns:
        bool: True if cookies were saved, False otherwise
    """
    global _cookie_manager
    if _cookie_manager:
        return _cookie_manager.save_cookies(force=force)
    else:
        logger.warning("No cookie manager available for manual save")
        return False

def load_config(config_path: str | Path = "config.yml") -> dict:
    """Loads the YAML configuration file relative to the project root."""
    # Construct absolute path relative to the project root
    # This assumes the script is run from the project root or config_path is relative to root
    # If running context.py directly, adjust ROOT_PATH or config_path accordingly
    if isinstance(config_path, str):
        config_path = Path(config_path)

    if not config_path.is_absolute():
         absolute_config_path = ROOT_PATH / config_path
    else:
         absolute_config_path = config_path

    logger.debug(f"Attempting to load config from: {absolute_config_path}")
    try:
        with open(absolute_config_path, 'r') as f:
            config = yaml.safe_load(f)
            # Basic validation
            if not config or 'credentials' not in config or 'runtime' not in config:
                raise ValueError("Config file is missing required sections ('credentials', 'runtime').")
            if 'username' not in config['credentials'] or 'password' not in config['credentials']:
                 raise ValueError("Config file is missing 'username' or 'password' under 'credentials'.")
            logger.info(f"Configuration loaded successfully from {absolute_config_path}.")
            return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found at: {absolute_config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration file: {e}")
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {e}")
        raise


def _perform_login(page: Page, context: BrowserContext, config: dict, cookie_path: Path):
    """Handles the interactive login process (synchronous)."""
    logger.info("Login required. Attempting interactive login...")
    username = config['credentials']['username']
    password = config['credentials']['password']
    accept_cookies_selector = config.get('runtime', {}).get('accept_cookies_selector')
    remember_me_button_selector = "#rememberme-div > div.memberList-container > div > div > div.member-profile-container.list-box > div.member-profile-block > button"

    try:
        # Handle cookie consent banner (often appears before login elements)
        if accept_cookies_selector:
            try:
                logger.debug(f"Looking for cookie consent banner: {accept_cookies_selector}")
                accept_button = page.locator(accept_cookies_selector)
                if accept_button.is_visible(timeout=5000):
                     logger.info("Cookie consent banner found, clicking accept.")
                     accept_button.click(timeout=5000)
                else:
                     logger.debug("Cookie consent banner not visible within timeout.")
            except PlaywrightTimeoutError:
                logger.warning("Cookie consent banner check timed out or button not visible.")
            except Exception as e:
                 logger.warning(f"Error handling cookie consent: {e}. Continuing login attempt.")

        # --- Check for 'Remember Me' button first --- #
        logger.debug(f"Checking for 'Remember Me' button: {remember_me_button_selector}")
        remember_me_button = page.locator(remember_me_button_selector)
        remember_me_clicked = False
        try:
             if remember_me_button.is_visible(timeout=3000): # Short check
                  logger.info("Found 'Remember Me' button, clicking it to log in.")
                  remember_me_button.click(timeout=5000)
                  remember_me_clicked = True
             else:
                  logger.debug("'Remember Me' button not found or not visible.")
        except PlaywrightTimeoutError:
            logger.debug("'Remember Me' button check timed out (not visible).")
        except Exception as e:
            logger.warning(f"Error checking for 'Remember Me' button: {e}")

        # --- Proceed with standard login if 'Remember Me' was not clicked --- #
        if not remember_me_clicked:
            logger.info("Proceeding with standard email/password login.")
            # Define selectors
            home_signin_button_selector = '[data-test-id="home-hero-sign-in-cta"]'
            email_input_selector = page.get_by_role('textbox', name='Email or phone')
            password_input_selector = page.get_by_role('textbox', name='Password')
            signin_button_selector = page.get_by_role('button', name='Sign in', exact=True)

            # Check if we need to click the initial sign-in button (if on homepage)
            # This check might be less relevant now we navigate directly to /feed, but keep as fallback
            if not email_input_selector.is_visible(timeout=5000):
                 logger.debug("Email input not immediately visible. Checking for potential homepage sign-in button.")
                 home_button = page.locator(home_signin_button_selector)
                 if home_button.is_visible(timeout=5000):
                    logger.info("Homepage Sign in CTA found, clicking it.")
                    home_button.click(timeout=5000)
                 else:
                     # If neither email input nor homepage button found quickly, wait a bit longer for login page elements
                     logger.warning("Could not find email input or homepage sign-in button quickly. Waiting for login form elements...")
                     try:
                         email_input_selector.wait_for(state="visible", timeout=10000) # Wait longer here
                     except PlaywrightTimeoutError:
                         logger.error("Login form (email input) did not appear after extended wait.")
                         raise Exception("Login form did not load correctly.")
            else:
                logger.debug("Email input visible.")

            # Fill credentials
            logger.debug("Waiting for email input field to be ready...")
            email_input_selector.wait_for(state="visible", timeout=15000)
            logger.info("Filling login credentials.")
            email_input_selector.fill(username)
            password_input_selector.fill(password)

            logger.info("Clicking Sign In button.")
            signin_button_selector.click(timeout=10000)
        # --- End of standard login block ---

        # Wait for successful login navigation (applies to both 'Remember Me' and standard login)
        logger.info("Waiting for successful login navigation to /feed/...")
        try:
             page.wait_for_url("**/feed/**", timeout=45000, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
             if "checkpoint/challenge" in page.url or "login/challenge" in page.url:
                  logger.error("Login resulted in a security check/challenge page. Manual intervention required.")
                  raise Exception("Login failed: Security Check/Challenge encountered.")
             else:
                  logger.error("Login failed: Timeout waiting for navigation to /feed/.")
                  # Consider saving screenshot page.screenshot(path=ROOT_PATH / "login_feed_timeout.png")
                  raise Exception("Login failed due to timeout after submitting credentials.")

        logger.info("Login successful. Saving session cookies.")
        # Create and set up cookie manager for dynamic saving
        save_interval = config.get('runtime', {}).get('cookie_save_interval', 120)
        cookie_manager = CookieManager(context, cookie_path, save_interval)
        set_cookie_manager(cookie_manager)
        
        # Initial save after login
        cookie_manager.save_cookies(force=True)
        logger.info(f"Cookies saved to {cookie_path} with dynamic management enabled (interval: {save_interval}s)")

    except PlaywrightTimeoutError as e:
        error_message = f"Login failed: Timeout interacting with login elements. Error: {e}"
        logger.error(error_message)
        # page.screenshot(path=ROOT_PATH / "login_interaction_timeout_error.png")
        raise Exception(error_message) from e
    except Exception as e:
        error_message = f"An unexpected error occurred during login: {e}"
        logger.error(error_message)
        # page.screenshot(path=ROOT_PATH / "login_unexpected_error.png")
        raise Exception(error_message) from e

def get_authenticated_page(playwright: Playwright, config: dict) -> Page:
    """
    Ensures the user is logged into LinkedIn, either via cookies or interactive login (synchronous).

    Args:
        playwright: The Playwright instance from sync_playwright().
        config: The loaded configuration dictionary.

    Returns:
        A Playwright Page object authenticated into LinkedIn.

    Raises:
        Exception: If login fails or configuration is invalid.
        ValueError: If config is invalid.
    """
    if not config or 'credentials' not in config or 'username' not in config['credentials']:
         raise ValueError("Invalid configuration provided to get_authenticated_page.")

    username = config['credentials']['username']
    # Sanitize username for filename (replace common invalid chars)
    safe_username = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in username)
    headless = config.get('runtime', {}).get('headless', True)
    cookie_dir = ROOT_PATH / "linkedin_auto_apply" / "cookies"
    cookie_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = cookie_dir / f"{safe_username}.json"

    storage_state = str(cookie_path) if cookie_path.exists() else None
    if storage_state:
        logger.info(f"Attempting to load browser state from: {cookie_path}")
    else:
        logger.info("No saved browser state found. Will perform interactive login if necessary.")

    browser = None # Initialize browser to None for cleanup block
    try:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=storage_state)
        page = context.new_page()

        logger.info("Navigating directly to LinkedIn feed page (https://www.linkedin.com/feed/)...")
        try:
             page.goto("https://www.linkedin.com/feed/", wait_until='domcontentloaded', timeout=60000)
             logger.info(f"Current URL after navigation attempt: {page.url}")
        except PlaywrightTimeoutError as nav_err:
             # Handle cases where even the initial navigation to /feed fails (network issue, etc.)
             logger.error(f"Timeout navigating to /feed/ initially: {nav_err}")
             if browser and browser.is_connected():
                  browser.close()
             raise Exception("Failed to load LinkedIn feed page due to timeout.") from nav_err

        # Check login status with a small delay for redirects
        page.wait_for_timeout(2000)
        is_logged_in = "/feed/" in page.url

        if not is_logged_in:
             logger.info("Not on feed page URL. Login required or cookie invalid.")
             _perform_login(page, context, config, cookie_path)
             # Re-verify login succeeded
             try:
                 page.wait_for_url("**/feed/**", timeout=15000, wait_until="domcontentloaded")
                 logger.info("Login verification successful (URL contains /feed/).")
             except PlaywrightTimeoutError:
                 logger.error("Login seemed successful but verification failed (not on /feed/ URL).")
                 # page.screenshot(path=ROOT_PATH / "login_verification_failed.png")
                 raise Exception("Login verification failed after interactive login.")
        else:
            logger.info("Already logged in via saved cookies (URL contains /feed/).")
            # Set up cookie manager for existing session
            save_interval = config.get('runtime', {}).get('cookie_save_interval', 120)
            cookie_manager = CookieManager(context, cookie_path, save_interval)
            set_cookie_manager(cookie_manager)
            logger.info(f"Dynamic cookie management enabled for existing session (interval: {save_interval}s)")

        return page # Return the page, caller manages browser/context closure

    except (PlaywrightTimeoutError, Exception) as e: # Catch specific and general exceptions
        error_message = f"Error during authentication/navigation: {e}"
        logger.error(error_message)
        # Attempt to capture screenshot before closing
        # if 'page' in locals():
        #     try:
        #          page.screenshot(path=ROOT_PATH / "auth_navigation_error.png")
        #     except Exception as screen_err:
        #          logger.error(f"Failed to take error screenshot: {screen_err}")
        if browser and browser.is_connected():
             browser.close() # Ensure browser is closed on error
        # Re-raise a general exception for the caller
        if isinstance(e, PlaywrightTimeoutError):
            raise Exception("Operation timed out during LinkedIn authentication/navigation.") from e
        else:
            raise Exception(f"An unexpected error occurred during LinkedIn authentication: {e}") from e


# Example synchronous usage (for testing purposes)
def main_sync_test():
    try:
        # Adjust config path relative to the actual execution context if needed
        # Assuming execution from project root:
        config_file_path = ROOT_PATH / "linkedin_auto_apply" / "config.yml"
        app_config = load_config(config_file_path)

        with sync_playwright() as p:
            logger.info("Launching browser context (sync)...")
            authenticated_page = get_authenticated_page(p, app_config)
            logger.info(f"Successfully obtained authenticated page (sync). Current URL: {authenticated_page.url}")

            logger.info("Keeping browser open for 10 seconds for verification (sync)...")
            authenticated_page.wait_for_timeout(10000)

            logger.info("Closing browser (sync)...")
            authenticated_page.context.browser.close()
            logger.info("Browser closed (sync).")

    except Exception as e:
        logger.error(f"An error occurred during the example sync run: {e}", exc_info=True)

if __name__ == "__main__":
    # Running the synchronous test function
    print("Running example sync usage... Ensure config.yml is correctly placed and filled.")
    print(f"Project Root (expected): {ROOT_PATH}")
    main_sync_test() 