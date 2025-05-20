import logging
import time
import sys
import os
from tkinter import messagebox
from playwright.sync_api import sync_playwright, Page, Playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError # More specific import
from pathlib import Path # Added for ROOT_PATH calculation
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Assuming context.py and search.py are in sibling directories (browser/, joblist/)
from browser.context import load_config, get_authenticated_page
from joblist.search import construct_search_url
from joblist.scroll_loader import load_all_job_cards # Import the new function
from apply import ApplicationWizard, APPLICATION_SUCCESS, APPLICATION_FAILURE, APPLICATION_INCOMPLETE

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
from typing import List, Dict, Optional # Added Optional


def run_profile_search(page: Page, profile: dict, config: dict) -> Optional[List[Dict[str, str]]]:
    """Constructs URL, navigates, scrolls, and extracts job data.
    
    Returns:
        List[Dict[str, str]]: A list of job data dictionaries if successful, None otherwise.
    """
    profile_name = profile.get('name', 'Unnamed Profile')
    current_query = profile.get('query', 'N/A') # Get current query for logging
    logger.info(f"--- Starting search for profile: {profile_name} (Query: '{current_query}') ---")
    try:
        search_url = construct_search_url(profile) # construct_search_url will use profile['query']
        if not search_url: # Handle case where construct_search_url returns None (e.g. missing keys)
            logger.error(f"FAILED: Could not construct search URL for profile '{profile_name}' with query '{current_query}'.")
            return None
            
        logger.info(f"Navigating to search URL: {search_url}")
        page.goto(search_url, wait_until='load', timeout=60000)
        logger.info(f"Base navigation complete for '{profile_name}' (Query: '{current_query}'). Waiting briefly...")
        page.wait_for_timeout(5000)
        logger.info(f"Waited after navigation. Current URL: {page.url}")

        # --- Scroll and Extract Job Data ---
        logger.info(f"Attempting to scroll and load job cards for profile '{profile_name}' (Query: '{current_query}')...")
        try:
            if not page.context or not page.context.browser or not page.context.browser.is_connected():
                 logger.error(f"Browser disconnected before scrolling for '{profile_name}' (Query: '{current_query}').")
                 return None

            # Load job cards using the refined function
            job_data_list: List[Dict[str, str]] = load_all_job_cards(
                page=page
            )

            if not job_data_list:
                logger.warning(f"No job data extracted for profile '{profile_name}' (Query: '{current_query}').")
                return [] # Return empty list if no jobs, to differentiate from error
            else:
                job_count = len(job_data_list)
                if job_count > 0:
                     logger.info(f"SUCCESS: Found {job_count} unique job cards after scrolling for profile '{profile_name}' (Query: '{current_query}').")
                     # --- Print Extracted Job Details ---
                     logger.info(f"--- Job Details for Profile: {profile_name} (Query: '{current_query}') ---")
                     for i, job in enumerate(job_data_list):
                         print(f"  Job {i+1}:")
                         print(f"    Title: {job.get('title', 'N/A')}")
                         print(f"    Company: {job.get('company', 'N/A')}")
                         print(f"    Link: {job.get('link', '#')}")
                         print("-" * 20)
                     logger.info(f"--- End Job Details for Profile: {profile_name} (Query: '{current_query}') ---")
                     return job_data_list
                else:
                     logger.warning(f"No unique job cards extracted after scrolling for profile '{profile_name}' (Query: '{current_query}').")
                     return []

        except Exception as scroll_err:
             logger.error(f"FAILED: Error during job card scrolling/loading for profile '{profile_name}' (Query: '{current_query}'): {scroll_err}", exc_info=True)
             return None

        logger.info(f"--- Finished processing profile: {profile_name} (Query: '{current_query}') ---") # This might be redundant if returning job_data_list
        return [] # Should have returned job_data_list or None by now

    except ValueError as e: # This was for construct_search_url, now handled above
         logger.error(f"FAILED: Error related to search URL construction for profile '{profile_name}' (Query: '{current_query}'): {e}")
         return None
    except PlaywrightTimeoutError as e:
         logger.error(f"FAILED: Timeout during navigation or initial load for profile '{profile_name}' (Query: '{current_query}'): {e}")
         return None
    except Exception as e:
        if "Target page, context or browser has been closed" in str(e):
             logger.error(f"FAILED: Browser closed unexpectedly during setup for profile '{profile_name}' (Query: '{current_query}'): {e}")
        else:
            logger.error(f"FAILED: An unexpected error occurred during search setup for profile '{profile_name}' (Query: '{current_query}'): {e}", exc_info=True)
        return None

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
            # Path to answers file, assuming it's in a standard location relative to ROOT_PATH
            # Adjust this path if your answers.json is located elsewhere.
            answers_path = ROOT_PATH / "linkedin_auto_apply" / "answers" / "default.json"
            if not answers_path.exists():
                logger.warning(f"Answers file not found at {answers_path}. Some features might not work as expected.")


            # Define a flag to check if application limit was reached
            application_limit_reached = False
            
            for profile_config in search_profiles:
                if application_limit_reached:
                    logger.info("Skipping remaining profiles due to application limit being reached.")
                    break
                    
                profile_name = profile_config.get('name', 'Unnamed Profile')
                original_query_string = profile_config.get('query', '')
                
                # Allow empty queries - they'll be handled by search.py
                if not original_query_string:
                    logger.info(f"Profile '{profile_name}' has an empty 'query' field. Will search by location only.")
                    search_terms = [''] # Use a single empty term for location-only search
                else:
                    search_terms = [term.strip() for term in original_query_string.split(',') if term.strip()]
                    
                    # If all terms were just whitespace, use a single empty term
                    if not search_terms:
                        logger.info(f"Profile '{profile_name}' has only whitespace in query: '{original_query_string}'. Will search by location only.")
                        search_terms = ['']
                
                logger.info(f"Processing profile '{profile_name}' with search terms: {search_terms}")
                
                overall_profile_success_flag = False # Tracks if any term in this profile led to successful applications

                for term_index, current_term in enumerate(search_terms):
                    logger.info(f"--- Starting processing for term {term_index + 1}/{len(search_terms)}: '{current_term}' in profile '{profile_name}' ---")
                    
                    # Create a temporary profile dictionary for the current search term
                    term_specific_profile = profile_config.copy()
                    term_specific_profile['query'] = current_term # Set the specific query for this run
                    
                    try:
                        # run_profile_search now returns a list of job data or None
                        job_data_list_for_term = run_profile_search(page, term_specific_profile, config)
                    except SystemExit as e:
                        # Catch the sys.exit(100) from scroll_loader.py
                        if e.code == 100:
                            logger.critical("LinkedIn Easy Apply application limit reached. Terminating the application process.")
                            application_limit_reached = True
                            messagebox.showwarning("Application Limit Reached", 
                                                 "You've reached the LinkedIn Easy Apply application limit for today.\n\n"
                                                 "LinkedIn allows a limited number of Easy Apply applications per day.\n"
                                                 "Please try again tomorrow.")
                            break
                        else:
                            # For other exit codes, re-raise
                            raise

                    if job_data_list_for_term is not None and job_data_list_for_term: # Check for non-None and non-empty list
                        logger.info(f"Found {len(job_data_list_for_term)} jobs for term '{current_term}'. Initializing application process...")
                        
                        #   !!! IMPORTANT !!!
                        #   Instantiate and use your ApplicationWizard here.
                        #   It should process the 'job_data_list_for_term'.
                        #   Example:
                        #   --------------------------------------------------------------------
                        #   wizard = ApplicationWizard(page, config, answers_path) # Or however you init your wizard
                        #   term_applications_successful = 0
                        #   for job_data in job_data_list_for_term:
                        #       try:
                        #           logger.info(f"Attempting to apply for job: {job_data.get('title')} at {job_data.get('company')}")
                        #           status = wizard.apply_to_job(job_data) # Your wizard's application method
                        #           if status == APPLICATION_SUCCESS: # Assuming these constants exist
                        #               term_applications_successful += 1
                        #               overall_profile_success_flag = True # Mark success if at least one app is good
                        #           elif status == APPLICATION_FAILURE:
                        #               logger.warning(f"Application failed for job: {job_data.get('title')}")
                        #           elif status == APPLICATION_INCOMPLETE:
                        #               logger.info(f"Application incomplete for job: {job_data.get('title')}")
                        #       except Exception as app_err:
                        #           logger.error(f"Error during application for job {job_data.get('title')}: {app_err}", exc_info=True)
                        #   logger.info(f"Completed application attempts for term '{current_term}'. Successful applications: {term_applications_successful}/{len(job_data_list_for_term)}")
                        #   --------------------------------------------------------------------
                        #   Replace the above example with your actual ApplicationWizard logic.
                        #   For now, we'll just log that jobs were found and would be processed.
                        logger.info(f"Placeholder: ApplicationWizard would process {len(job_data_list_for_term)} jobs for term '{current_term}'.")
                        # Simulate some success for testing the loop structure
                        if job_data_list_for_term : overall_profile_success_flag = True


                    elif job_data_list_for_term is None: # Explicit error from run_profile_search
                         logger.error(f"Search failed for term '{current_term}' in profile '{profile_name}'. See previous errors.")
                    else: # Empty list returned, meaning no jobs found
                        logger.info(f"No jobs found for term '{current_term}' in profile '{profile_name}'.")

                    # Delay between terms if there are more terms to process for this profile
                    if term_index < len(search_terms) - 1:
                        delay_between_terms_ms = config.get('runtime', {}).get('delay_between_terms_ms', 5000) # Default to 5s
                        logger.info(f"Waiting for {delay_between_terms_ms / 1000.0:.1f}s before processing next term...")
                        time.sleep(delay_between_terms_ms / 1000.0)
                
                profile_results[profile_name] = overall_profile_success_flag
                if not overall_profile_success_flag:
                     # exit_code = 1 # Decide if a profile with no successful terms makes the whole run fail
                     logger.warning(f"Profile '{profile_name}' completed but no terms led to successful job processing/applications.")
                else:
                    logger.info(f"Profile '{profile_name}' completed successfully with at least one term processed.")

                # Delay between profiles (this was the original delay)
                # Consider if this is still needed or if the per-term delay is sufficient.
                # For safety, keeping it but you might want to adjust/remove.
                logger.info(f"Finished all terms for profile '{profile_name}'. Waiting before next profile (if any)...")
                time.sleep(config.get('runtime', {}).get('random_delay_ms', [1000, 3000])[0] / 1000.0)

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
    except SystemExit as e:
        if e.code == 100:
            logger.critical("LinkedIn Easy Apply application limit reached. Terminating the application process.")
            exit_code = 100
        else:
            # Re-raise other SystemExit exceptions
            raise
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