import logging
import time
from playwright.sync_api import sync_playwright, Page, Playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError # More specific import
from pathlib import Path # Added for ROOT_PATH calculation

# Assuming context.py and search.py are in sibling directories (browser/, joblist/)
# Adjust imports based on your final structure if different
from browser.context import load_config, get_authenticated_page
from joblist.search import construct_search_url
from joblist.scroll_loader import load_all_job_cards # Import the new function
from apply.wizard import ApplicationWizard

# Define root path relative to this file (main.py)
ROOT_PATH = Path(__file__).parent.parent

# Configure logging (consistent level, maybe configure format via Loguru later)
# Basic config for now
log_level_str = 'INFO' # Default, will be updated from config
logging.basicConfig(level=log_level_str, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Define selectors for search results verification
JOB_LIST_SELECTOR = 'ul.jobs-search-results__list, div.jobs-search-results-list' # Prioritize list, fallback div


# Import List and Dict for type hinting
from typing import List, Dict


def run_profile_search(page: Page, profile: dict, config: dict):
    """Constructs URL, navigates, scrolls, and extracts job data."""
    profile_name = profile.get('name', 'Unnamed Profile')
    logger.info(f"--- Starting search for profile: {profile_name} ---")
    # headless = config.get('runtime', {}).get('headless', True) # Not directly used here
    try:
        search_url = construct_search_url(profile)
        logger.info(f"Navigating to search URL: {search_url}")
        page.goto(search_url, wait_until='load', timeout=60000)
        logger.info(f"Base navigation complete for '{profile_name}'. Waiting briefly...")
        page.wait_for_timeout(5000)
        logger.info(f"Waited after navigation. Current URL: {page.url}")

        # --- Scroll and Extract Job Data ---
        logger.info(f"Attempting to scroll and load job cards for profile '{profile_name}'...")
        try:
            if not page.context or not page.context.browser or not page.context.browser.is_connected():
                 logger.error(f"Browser disconnected before scrolling for '{profile_name}'.")
                 return False # Treat as profile failure

            # Load job cards using the refined function
            logger.info(f"Attempting to scroll and load job cards for profile '{profile_name}'...")
            job_data_list: List[Dict[str, str]] = load_all_job_cards(
                page=page # Only pass the page object now
            )

            if not job_data_list:
                logger.warning(f"No job data extracted for profile '{profile_name}'. Skipping.")
            else:
                job_count = len(job_data_list) # Get count from the returned list

                if job_count > 0:
                     logger.info(f"SUCCESS: Found {job_count} unique job cards after scrolling for profile '{profile_name}'.")
                     # --- Print Extracted Job Details ---
                     logger.info(f"--- Job Details for Profile: {profile_name} ---")
                     for i, job in enumerate(job_data_list):
                         print(f"  Job {i+1}:")
                         print(f"    Title: {job.get('title', 'N/A')}")
                         print(f"    Company: {job.get('company', 'N/A')}")
                         print(f"    Link: {job.get('link', '#')}")
                         # print(f"    ID: {job.get('job_id', 'N/A')}") # Optional: print ID
                         print("-" * 20)
                     logger.info(f"--- End Job Details for Profile: {profile_name} ---")
                     # --- Placeholder for next steps (e.g., applying) ---
                     # You would now iterate through job_data_list for application logic
                else:
                     # *** MODIFIED: Updated warning message ***
                     logger.warning(f"No unique job cards extracted after scrolling for profile '{profile_name}'. The page might be empty, selectors might need adjustment, or scrolling parameters might need tuning.")
                     # Screenshot logic remains the same if needed

        except Exception as scroll_err:
             logger.error(f"FAILED: Error during job card scrolling/loading for profile '{profile_name}': {scroll_err}", exc_info=True)
             return False # Treat scrolling failure as profile failure

        logger.info(f"--- Finished processing profile: {profile_name} ---")
        return True # Indicate success for this profile

    except ValueError as e:
         logger.error(f"FAILED: Could not construct search URL for profile '{profile_name}': {e}")
         return False
    except PlaywrightTimeoutError as e:
         logger.error(f"FAILED: Timeout during navigation or initial load for profile '{profile_name}': {e}")
         return False
    except Exception as e:
        # Catch browser closed errors specifically if they happen here
        if "Target page, context or browser has been closed" in str(e):
             logger.error(f"FAILED: Browser closed unexpectedly during setup for profile '{profile_name}': {e}")
        else:
            logger.error(f"FAILED: An unexpected error occurred during search setup for profile '{profile_name}': {e}", exc_info=True)
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