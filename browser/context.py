import yaml
import json
from pathlib import Path
import logging
# Use sync_api for synchronous execution as initially requested
from playwright.sync_api import sync_playwright, Playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
# Keep async imports for the example usage block if needed, or remove if sticking purely to sync
from playwright.async_api import async_playwright
import asyncio
import time
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define root path relative to this file
# Assuming this file is in linkedin_auto_apply/browser/
ROOT_PATH = Path(__file__).parent.parent.parent

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
        context.storage_state(path=str(cookie_path))
        logger.info(f"Cookies saved to {cookie_path}")

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