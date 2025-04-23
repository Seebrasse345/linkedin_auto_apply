import logging
import time
from playwright.sync_api import sync_playwright, Page, Playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError # More specific import
from pathlib import Path # Added for ROOT_PATH calculation

# Assuming context.py and search.py are in sibling directories (browser/, joblist/)
# Adjust imports based on your final structure if different
from browser.context import load_config, get_authenticated_page
from joblist.search import construct_search_url

# Define root path relative to this file (main.py)
ROOT_PATH = Path(__file__).parent.parent

# Configure logging (consistent level, maybe configure format via Loguru later)
# Basic config for now
log_level_str = 'INFO' # Default, will be updated from config
logging.basicConfig(level=log_level_str, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Define selectors for search results verification
JOB_LIST_SELECTOR = 'ul.jobs-search-results__list, div.jobs-search-results-list' # Prioritize list, fallback div

def run_profile_search(page: Page, profile: dict, config: dict):
    """Constructs URL and navigates to the search results page for a profile."""
    profile_name = profile.get('name', 'Unnamed Profile')
    logger.info(f"--- Starting search for profile: {profile_name} ---")
    headless = config.get('runtime', {}).get('headless', True)
    try:
        search_url = construct_search_url(profile)
        logger.info(f"Navigating to search URL: {search_url}")
        page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        logger.info(f"Navigation complete for profile '{profile_name}'. Current URL: {page.url}")

        # Verify search results page loaded (check for job list container)
        try:
             logger.info(f"Verifying job list container is visible ({JOB_LIST_SELECTOR})...")
             page.locator(JOB_LIST_SELECTOR).first.wait_for(state="visible", timeout=15000)
             logger.info(f"SUCCESS: Job search results page verified for profile '{profile_name}'.")

             # Add a small pause for visibility during non-headless runs
             if not headless:
                pause_duration = 5 # seconds
                logger.debug(f"Running in non-headless mode. Pausing for {pause_duration} seconds...")
                time.sleep(pause_duration)

        except PlaywrightTimeoutError:
             logger.error(f"FAILED: Could not verify job list container ({JOB_LIST_SELECTOR}) after navigation for profile '{profile_name}'.")
             # Optionally, save screenshot: page.screenshot(path=ROOT_PATH / f"search_verify_fail_{profile_name}.png")
             # Continue to the next profile despite verification failure

        # --- Placeholder for next steps --- TODO: Integrate scrolling and card iteration
        logger.info(f"Placeholder: Scrolling and card iteration for profile '{profile_name}' would happen here.")
        # result = joblist.scroll_loader.load_all_cards(page)
        # if result:
        #    FOR card in joblist.card_iterator.cards(page, profile): ...
        # --- End Placeholder ---
        logger.info(f"--- Finished processing profile: {profile_name} ---")
        return True # Indicate success for this profile

    except ValueError as e:
         logger.error(f"FAILED: Could not construct search URL for profile '{profile_name}': {e}")
         return False
    except PlaywrightTimeoutError as e:
         logger.error(f"FAILED: Timeout during navigation or verification for profile '{profile_name}': {e}")
         # Optionally, save screenshot: page.screenshot(path=ROOT_PATH / f"search_nav_fail_{profile_name}.png")
         return False
    except Exception as e:
        logger.error(f"FAILED: An unexpected error occurred during search for profile '{profile_name}': {e}", exc_info=True)
        return False

def main():
    """Main application entry point."""
    start_time = time.time()
    logger.info("========= Starting LinkedIn Auto Apply Bot =========")
    page: Page | None = None # Initialize page to None for finally block
    browser_context = None # Keep track for closure
    config = {}
    exit_code = 0 # Default to success

    try:
        # Load configuration
        # Assuming config.yml is in the parent directory of this script (project root)
        config_path = ROOT_PATH / "linkedin_auto_apply" / "config.yml"
        config = load_config(config_path)
        logger.info("Configuration loaded successfully.")

        # Update logging level from config if specified
        log_level_str = config.get('runtime', {}).get('log_level', 'INFO').upper()
        try:
            logging.getLogger().setLevel(log_level_str)
            logger.info(f"Logging level set to {log_level_str}.")
        except ValueError:
            logger.warning(f"Invalid log_level '{log_level_str}' in config. Defaulting to INFO.")
            logging.getLogger().setLevel('INFO')


        with sync_playwright() as p:
            logger.info("Attempting LinkedIn authentication...")
            try:
                 page = get_authenticated_page(p, config) # This now returns the page
                 browser_context = page.context # Get context for later closure
                 logger.info("SUCCESS: Authentication successful!")
            except Exception as auth_err:
                 logger.error(f"CRITICAL: Authentication failed: {auth_err}", exc_info=True)
                 raise RuntimeError("Authentication failed, cannot proceed.") from auth_err # Re-raise as critical failure

            # --- Process Search Profiles --- TODO: Add profile-specific error tracking/summary
            search_profiles = config.get('search_profiles', [])
            if not search_profiles:
                logger.warning("No search profiles found in configuration. Exiting.")
                return # Nothing to do

            profile_results = {} # Store success/failure per profile
            for profile in search_profiles:
                 success = run_profile_search(page, profile, config)
                 profile_results[profile.get('name', 'Unnamed Profile')] = success
                 if not success:
                      exit_code = 1 # Mark run as failed if any profile fails
                 time.sleep(config.get('runtime', {}).get('random_delay_ms', [1000, 3000])[0] / 1000.0) # Small delay between profiles

            logger.info("--- Summary of Profile Runs ---")
            for name, status in profile_results.items():
                logger.info(f"Profile '{name}': {'SUCCESS' if status else 'FAILED'}")
            logger.info("---------------------------------")


    except FileNotFoundError as e:
        logger.error(f"CRITICAL: Configuration file not found at expected location: {config_path}")
        exit_code = 1
    except RuntimeError as e:
        # Already logged in the authentication block
        logger.error(f"Runtime error: {e}")
        exit_code = 1
    except Exception as e:
        logger.error(f"CRITICAL: An unexpected error occurred in the main process: {e}", exc_info=True)
        exit_code = 1

    finally:
        if browser_context and browser_context.browser.is_connected():
            try:
                 logger.info("Closing browser...")
                 browser_context.browser.close()
                 logger.info("Browser closed.")
            except Exception as close_err:
                 logger.error(f"Error closing browser: {close_err}")
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"========= LinkedIn Auto Apply Bot finished in {duration:.2f} seconds ========= ")
        # Consider sys.exit(exit_code) if running as a script/CLI tool


if __name__ == "__main__":
    main() 