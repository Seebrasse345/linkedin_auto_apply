import logging
import time
import random
import re
import os
import json
from playwright.sync_api import Page, Locator, Error as PlaywrightError
from typing import List, Dict, Set, Optional
from apply import ApplicationWizard, APPLICATION_SUCCESS, APPLICATION_FAILURE, APPLICATION_INCOMPLETE
from browser.context import load_config

logger = logging.getLogger(__name__)

# Path to config file
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yml')

# Selectors (Adjust based on LinkedIn structure)
SCROLL_CONTAINER_SELECTOR = "div.jobs-search-results-list" # Updated selector for the scrollable job list container
JOB_CARD_SELECTOR = "li.scaffold-layout__list-item" # The list item containing the card
# Combine potential selectors, Playwright takes the first match
JOB_LINK_SELECTOR = "a.job-card-container__link, a.job-card-list__title" 
JOB_TITLE_SELECTOR = f"{JOB_LINK_SELECTOR} strong" # Title often within strong tag inside the link
# Separate company selectors for sequential fallback
JOB_COMPANY_SELECTOR_PRIMARY = "span.job-card-container__primary-description"
JOB_COMPANY_SELECTOR_SECONDARY = "a.job-card-container__company-name" 

# Pagination selectors
PAGINATION_CONTAINER_SELECTOR = 'div.jobs-search-pagination'
PAGINATION_NEXT_BUTTON_SELECTOR = 'button.jobs-search-pagination__button--next, button[aria-label="View next page"]'
PAGINATION_PAGE_INDICATOR_SELECTOR = 'p.jobs-search-pagination__page-state'

# Used for waiting after pagination click
JOB_LIST_SELECTOR = 'ul.jobs-search-results__list, div.jobs-search-results-list'

# Default settings
SCROLL_INCREMENT = 3  # Scroll every Nth card (increased for faster scrolling)
MAX_SCROLL_ATTEMPTS = 20 # Max scroll attempts to prevent infinite loops (reduced from 30)
SCROLL_STABILITY_CHECKS = 2 # Stop if DOM count is stable for this many checks (reduced from 3)
POST_SCROLL_DELAY_MS = 400 # Delay after each scroll_into_view (reduced from 800ms)
EXTRACT_TIMEOUT_MS = 2500 # Timeout for extracting text/attributes from elements (reduced from 3000ms)
QUICK_EXTRACT_TIMEOUT_MS = 800 # Faster timeout for individual fields (reduced from 1000ms)
INITIAL_WAIT_MS = 1000 # Wait briefly for initial cards to appear (reduced from 1500ms)

# --- Selectors --- 
# For the Job List Items (Scrolling & Clicking)
DETAILS_PANE_TITLE_SELECTOR = ".job-details-jobs-unified-top-card__job-title"
DETAILS_PANE_COMPANY_SELECTOR = ".job-details-jobs-unified-top-card__company-name a" # Link inside company name
DETAILS_PANE_LOCATION_SELECTOR = ".job-details-jobs-unified-top-card__primary-description-without-tagline span.job-details-jobs-unified-top-card__bullet" # Location often uses bullets
# Job description selectors - multiple options to handle LinkedIn UI variations
DETAILS_PANE_DESCRIPTION_SELECTOR = ".jobs-description-content__text, .jobs-description-content__text--stretch, #job-details"
DETAILS_PANE_EASY_APPLY_BUTTON_SELECTOR = 'button.jobs-apply-button span.artdeco-button__text'
DETAILS_PANE_APPLY_BUTTON_SELECTOR = 'button.jobs-apply-button'

# --- Settings --- 
POST_CLICK_DELAY_MS = 500 # Wait after clicking a card for pane to load (reduced from 1000ms)

# File paths for previously processed applications
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
SUCCESSFUL_APPLICATIONS_FILE = os.path.join(DATA_DIR, 'successful_applications.json')
FAILED_APPLICATIONS_FILE = os.path.join(DATA_DIR, 'failed_applications.json')

def extract_job_id_from_url(url: str) -> str | None:
    """Helper to extract job ID from common LinkedIn job URL patterns."""
    try:
        # Example pattern: /jobs/view/1234567890/?...
        parts = url.split('/jobs/view/')
        if len(parts) > 1:
            return parts[1].split('/')[0].split('?')[0]
    except Exception:
        pass # Ignore errors during extraction
    return None

def _extract_job_id(card: Locator) -> Optional[str]:
    """Extracts job ID from card attributes."""
    job_id = None
    try:
        # Try data-job-id first (often on the container inside li)
        container = card.locator('div.job-card-container').first
        if container:
            job_id = container.get_attribute('data-job-id', timeout=500)
        
        # Fallback: try data-entity-urn on the li
        if not job_id:
            urn = card.get_attribute('data-entity-urn', timeout=500)
            if urn and 'jobPosting:' in urn:
                job_id = urn.split(':')[-1]
                
        # Fallback 2: try job ID from link href if present on card
        if not job_id:
             link_element = card.locator("a.job-card-container__link, a.job-card-list__title").first
             if link_element:
                 job_url = link_element.get_attribute('href', timeout=500)
                 if job_url:
                     job_id_match = re.search(r'/jobs/view/(\d+)/', job_url)
                     if job_id_match:
                         job_id = job_id_match.group(1)
                         
    except PlaywrightError as e:
        logger.debug(f"Quick Job ID extraction failed for card: {e}")
    return job_id

def contains_banned_words(job_title: str, banned_words: List[str]) -> bool:
    """Check if a job title contains any of the banned words.
    
    Args:
        job_title: The job title to check.
        banned_words: List of banned words/phrases to check against.
        
    Returns:
        True if the job title contains any banned words, False otherwise.
    """
    if not job_title or not banned_words:
        return False
        
    # Convert title to lowercase for case-insensitive comparison
    job_title_lower = job_title.lower()
    
    # Check if any banned word is in the job title
    for word in banned_words:
        if word.lower() in job_title_lower:
            logger.info(f"Job title '{job_title}' contains banned word '{word}'")
            return True
            
    return False

def load_previously_processed_jobs():
    """Load lists of successfully applied and failed applications from JSON files.
    
    Returns:
        A tuple of (successful_job_ids, failed_job_ids) as sets
    """
    successful_job_ids = set()
    failed_job_ids = set()
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Load successful applications
    try:
        if os.path.exists(SUCCESSFUL_APPLICATIONS_FILE):
            with open(SUCCESSFUL_APPLICATIONS_FILE, 'r') as f:
                successful_job_ids = set(json.load(f))
                logger.info(f"Loaded {len(successful_job_ids)} previously successful applications")
    except Exception as e:
        logger.error(f"Error loading successful applications: {e}")
    
    # Load failed applications
    try:
        if os.path.exists(FAILED_APPLICATIONS_FILE):
            with open(FAILED_APPLICATIONS_FILE, 'r') as f:
                failed_job_ids = set(json.load(f))
                logger.info(f"Loaded {len(failed_job_ids)} previously failed applications")
    except Exception as e:
        logger.error(f"Error loading failed applications: {e}")
    
    return successful_job_ids, failed_job_ids

def load_all_job_cards(page: Page):
    """Loads job cards via scrolling, then clicks each card to extract details from the main pane.
    
    1. Determines initial max number of job card elements in DOM.
    2. Scrolls cards at indices (0, SCROLL_INCREMENT, ...) up to that max count into view.
    3. Iterates through located cards, clicks each, waits for details pane, extracts.
    4. Checks for pagination at the bottom and navigates to next pages if available.
    5. Skips jobs with titles containing banned words from the config.
    
    Args:
        page: The Playwright Page object.
    
    Returns:
        A list of dictionaries containing details of unique job cards found.
    """
    job_data_list: List[Dict[str, str]] = []
    seen_job_ids: Set[str] = set()

    # Load config to get the banned words
    config = load_config(CONFIG_PATH)
    banned_words = config.get('banned_words', [])
    if banned_words:
        logger.info(f"Loaded {len(banned_words)} banned words from config: {', '.join(banned_words)}")
    else:
        logger.info("No banned words found in config")
    
    # Load previously processed job IDs
    successful_job_ids, failed_job_ids = load_previously_processed_jobs()
    previously_processed_ids = successful_job_ids.union(failed_job_ids)
    logger.info(f"Total {len(previously_processed_ids)} previously processed applications will be skipped")

    logger.info(f"Attempting to force-scroll job cards (increment: {SCROLL_INCREMENT}) up to initial DOM count...")
    page.wait_for_timeout(INITIAL_WAIT_MS) # Allow initial load

    # --- Determine Initial Max Count and Scroll Phase --- 
    initial_max_count = 0
    try:
        initial_max_count = len(page.locator(JOB_CARD_SELECTOR).all())
        if initial_max_count == 0:
            logger.warning("Initial DOM count is 0. No cards to scroll/extract.")
            return []
        logger.info(f"Initial DOM count detected: {initial_max_count} cards. Will scroll increments up to this index.")

        # Loop through increments based on the *initial* count to ensure scroll attempts
        scroll_target_index = 0
        for target_index in range(0, initial_max_count, SCROLL_INCREMENT):
            scroll_target_index = target_index # Keep track of last target
            logger.debug(f"--- Scrolling target index: {target_index}/{initial_max_count-1} ---")
            try:
                target_card = page.locator(JOB_CARD_SELECTOR).nth(target_index)
                logger.debug(f"Scrolling card at index {target_index} into view...")
                target_card.scroll_into_view_if_needed(timeout=EXTRACT_TIMEOUT_MS) 
                logger.debug(f"Waiting {POST_SCROLL_DELAY_MS}ms after scroll...")
                page.wait_for_timeout(POST_SCROLL_DELAY_MS)
            except PlaywrightError as pe:
                logger.warning(f"Playwright error during scroll targeting index {target_index}: {pe}. Skipping to next increment.")
                continue 
            except Exception as e:
                logger.error(f"Unexpected error during scroll targeting index {target_index}: {e}. Stopping scroll phase.")
                break 

    except Exception as e_init:
        logger.error(f"Error getting initial card count or during scroll loop setup: {e_init}")
        return [] # Cannot proceed if initial count fails

    logger.info(f"Forced incremental scrolling phase complete (attempted up to index {scroll_target_index}). Now extracting details by clicking cards.")

    # --- Extraction Phase (Click Card -> Extract from Details Pane) --- 
    try:
        # Re-locate all cards after scrolling is finished
        all_cards = page.locator(JOB_CARD_SELECTOR).all()
        final_card_count = len(all_cards)
        logger.info(f"Found {final_card_count} total job card elements in the DOM after scrolling phase for extraction.")

        if not all_cards:
             logger.warning("No job card elements found after scrolling phase finished. Check selectors or page state.")
             return []

        # Process ALL cards found after scrolling
        processed_count = 0
        added_count = 0
        for i, card in enumerate(all_cards):
            logger.info(f"Processing card {i+1}/{final_card_count}...")
            job_id = None
            try:
                # 1. Extract Job ID from card attribute first
                job_id = _extract_job_id(card)
                if not job_id:
                    logger.warning(f"  Card {i+1}: Could not extract Job ID from attributes. Skipping.")
                    continue
                
                if job_id in seen_job_ids:
                    logger.debug(f"  Skipping duplicate Job ID: {job_id}")
                    continue

                # Skip if this job was previously processed (successful or failed)
                if job_id in previously_processed_ids:
                    if job_id in successful_job_ids:
                        logger.info(f"  Skipping previously successful application - Job ID: {job_id}")
                    else:
                        logger.info(f"  Skipping previously failed application - Job ID: {job_id}")
                    processed_count += 1
                    continue
                
                # 2. Click the card to load details pane
                logger.debug(f"  Card {i+1} (ID: {job_id}): Clicking card...")
                card.click() # Potential race condition if page refreshes?
                logger.debug(f"  Card {i+1}: Waiting {POST_CLICK_DELAY_MS}ms for details pane to potentially load...")
                page.wait_for_timeout(POST_CLICK_DELAY_MS)
                
                # 3. Wait for a key element in the details pane (e.g., title) to confirm load
                logger.debug(f"  Card {i+1}: Waiting for details pane title selector: '{DETAILS_PANE_TITLE_SELECTOR}'")
                page.wait_for_selector(DETAILS_PANE_TITLE_SELECTOR, timeout=EXTRACT_TIMEOUT_MS)
                logger.debug(f"  Card {i+1}: Details pane title found.")
                
                # 4. Extract details from the details pane
                job_title = "N/A"
                company_name = "N/A"
                location = "N/A"
                job_description = "N/A"
                is_easy_apply = False
                job_url = page.url # URL after clicking card
                
                # Title
                try:
                    title_elem = page.locator(DETAILS_PANE_TITLE_SELECTOR).first
                    job_title = title_elem.inner_text(timeout=EXTRACT_TIMEOUT_MS // 2).strip()
                    
                    # Check if job title contains any banned words
                    if contains_banned_words(job_title, banned_words):
                        logger.info(f"  Card {i+1}: Skipping job with banned word in title: '{job_title}'")
                        continue  # Skip this job and move to the next one
                except PlaywrightError as e_title:
                    logger.warning(f"  Card {i+1}: Failed to extract title from details pane: {e_title}")
                
                # Company
                try:
                    company_elem = page.locator(DETAILS_PANE_COMPANY_SELECTOR).first
                    company_name = company_elem.inner_text(timeout=EXTRACT_TIMEOUT_MS // 2).strip()
                except PlaywrightError as e_company:
                     logger.warning(f"  Card {i+1}: Failed to extract company from details pane: {e_company}")

                # Location
                try:
                    # Location is often split, try getting parent container text
                    loc_container = page.locator(DETAILS_PANE_LOCATION_SELECTOR).first.locator('xpath=..') # Get parent
                    location = loc_container.inner_text(timeout=EXTRACT_TIMEOUT_MS // 2).strip()
                    location = re.sub(r'\s+', ' ', location) # Clean whitespace
                except Exception as e:
                    pass # Suppress warning as requested

                # Easy Apply Status
                try:
                    easy_apply_text_elem = page.locator(DETAILS_PANE_EASY_APPLY_BUTTON_SELECTOR).first
                    button_text = easy_apply_text_elem.inner_text(timeout=1000).strip()
                    if 'Easy Apply' in button_text:
                        is_easy_apply = True
                except PlaywrightError:
                    # If text element fails, check apply button existence as fallback
                    try:
                         if page.locator(DETAILS_PANE_APPLY_BUTTON_SELECTOR).is_visible(timeout=500):
                             # Cannot definitively say Easy Apply, assume False
                             logger.debug(f"  Card {i+1}: Apply button found, but not confirmed 'Easy Apply'.")
                         else: 
                              logger.debug(f"  Card {i+1}: No Apply button found.")
                    except PlaywrightError:
                        logger.debug(f"  Card {i+1}: Apply button check failed.")

                # Description (can be long, allow more time)
                job_description = ""
                desc_html = ""
                
                try:
                    # Try multiple selectors to find the job description
                    # First try the jobs-description container approach (newer UI)
                    job_desc_container = page.locator('article.jobs-description__container')
                    if job_desc_container.count() > 0:
                        try:
                            # Try to get the complete description HTML
                            desc_html = job_desc_container.inner_html(timeout=EXTRACT_TIMEOUT_MS * 2)
                            logger.info(f"Extracted job description HTML using container selector for job ID: {job_id}")
                            
                            # Extract text from the HTML
                            job_description = job_desc_container.inner_text(timeout=EXTRACT_TIMEOUT_MS).strip()
                        except Exception as container_err:
                            logger.debug(f"Container approach failed: {container_err}")
                    
                    # If we still don't have a description, try the targeted selector approach
                    if not job_description:
                        desc_elem = page.locator(DETAILS_PANE_DESCRIPTION_SELECTOR).first
                        job_description = desc_elem.inner_text(timeout=EXTRACT_TIMEOUT_MS * 2).strip()
                        
                        # Try to get the HTML content for better formatting
                        if not desc_html:
                            desc_html = desc_elem.inner_html(timeout=EXTRACT_TIMEOUT_MS)
                            logger.info(f"Extracted job description HTML using fallback selector for job ID: {job_id}")
                    
                    # Final fallback - try to get any text from the job details section
                    if not job_description:
                        logger.debug("Trying fallback method for job description")
                        fallback_desc = page.locator('#job-details, .jobs-box__html-content').inner_text(timeout=EXTRACT_TIMEOUT_MS)
                        if fallback_desc:
                            job_description = fallback_desc.strip()
                            desc_html = page.locator('#job-details, .jobs-box__html-content').inner_html(timeout=EXTRACT_TIMEOUT_MS)
                            logger.info(f"Extracted job description using last-resort fallback for job ID: {job_id}")
                except Exception as e:
                    logger.warning(f"Failed to extract job description for job ID {job_id}: {e}")
                
                # 5. Store data
                job_details = {
                    'job_id': job_id,
                    'title': job_title,
                    'company': company_name,
                    'location': location,
                    'posted_date': 'N/A', # Not easily available in details pane usually
                    'url': job_url, # URL when detail pane is visible
                    'easy_apply': is_easy_apply,
                    'description': job_description, # Store the full job description
                    'description_html': desc_html if 'desc_html' in locals() else ""
                }
                
                logger.info(
                    f"  -> Extracted Job: ID={job_id}, Title='{job_title}', "
                    f"Company='{company_name}', EasyApply={is_easy_apply}"
                )

                # --- Initiate Easy Apply if applicable --- 
                if is_easy_apply:
                    logger.info(f"    Attempting Easy Apply for Job ID: {job_id} ({job_title}) ...")
                    try:
                        # Click the Easy Apply button here (in scroll_loader) to avoid conflicts
                        # First, verify we have an Easy Apply button
                        easy_apply_button = page.locator(DETAILS_PANE_APPLY_BUTTON_SELECTOR)
                        if easy_apply_button.count() > 0:
                            # Use first() to handle multiple matching elements
                            logger.info(f"    Clicking Easy Apply button for Job ID: {job_id}")
                            easy_apply_button.first.click(timeout=3000)  # Reduced timeout from 5000ms
                            page.wait_for_timeout(1500)  # Wait for form to load (reduced from 2000ms)
                            
                            # Set flag indicating button was already clicked
                            job_details['easy_apply_clicked'] = True
                            
                            # Initialize the application wizard
                            wizard = ApplicationWizard(page)
                            
                            # Start the application process and wait for it to complete
                            logger.info(f"    Starting application wizard for Job ID: {job_id}")
                            application_status = wizard.start_application(job_details)
                            
                            # Check application status
                            if application_status == APPLICATION_SUCCESS:
                                logger.info(f"    Successfully applied to Job ID: {job_id}")
                                # Add a field to job_details to indicate success
                                job_details['application_status'] = 'success'
                            elif application_status == APPLICATION_FAILURE:
                                logger.warning(f"    Application failed for Job ID: {job_id}")
                                job_details['application_status'] = 'failure'
                            else:  # APPLICATION_INCOMPLETE
                                logger.warning(f"    Application incomplete for Job ID: {job_id}")
                                job_details['application_status'] = 'incomplete'
                                
                            # Wait for UI to settle after application
                            page.wait_for_timeout(1000)
                        else:
                            logger.warning(f"    No Easy Apply button found for Job ID: {job_id}")
                            job_details['application_status'] = 'not_applicable'
                            job_details['application_error'] = 'No Easy Apply button found'
                    except PlaywrightError as pe:
                        logger.error(f"    Playwright error during application process for Job ID {job_id}: {pe}")
                        job_details['application_status'] = 'error'
                        job_details['application_error'] = str(pe)
                    except Exception as e_apply:
                        logger.error(f"    Failed during application process for Job ID {job_id}: {e_apply}")
                        job_details['application_status'] = 'error'
                        job_details['application_error'] = str(e_apply)
                # --- End Easy Apply --- 
 
                job_data_list.append(job_details)
                seen_job_ids.add(job_id)
                added_count += 1
                processed_count += 1
                
            except PlaywrightError as pe_detail:
                logger.error(f"  PlaywrightError processing card {i+1} (ID: {job_id}): {pe_detail}")
                # Optionally add job_id to a separate failed list here if needed
                processed_count += 1 # Count as processed even if failed
            except Exception as e_card:
                logger.error(f"  Unexpected error processing card {i+1} (ID: {job_id}): {e_card}")
                processed_count += 1

        logger.info(f"Extraction phase complete for current page. Processed {processed_count}/{final_card_count} cards found, added {added_count} unique jobs.")
        
        # Check if there are more pages to navigate to
        all_pages_processed = check_and_navigate_to_next_page(page)
        if not all_pages_processed:
            # If we successfully navigated to a new page, recursively process that page
            logger.info("Processing jobs on the next page...")
            # No need for additional wait here as we've already done it in check_and_navigate_to_next_page
            
            # Need to start the extraction process from the beginning again for this new page
            # Refresh the cards list and process them
            logger.info("Starting to process cards on new page")
            return load_all_job_cards(page)  # Return the result directly for the new page processing
            
            # We're changing the approach here: instead of extending the list,
            # we're starting a completely fresh extraction on the new page
            # This ensures the process restarts properly for each page

    except Exception as e_extract_phase:
        logger.error(f"Error during the final extraction phase: {e_extract_phase}")
        return job_data_list # Return whatever was collected before the error

    return job_data_list


def check_and_navigate_to_next_page(page: Page) -> bool:
    """Checks if there are more pages of job results and navigates to the next page if available.
    
    Args:
        page: The Playwright Page object.
        
    Returns:
        bool: True if all pages have been processed (no more pages), False if navigated to a new page.
    """
    try:
        logger.info("Checking for pagination on current page...")
        # Ensure we're on the main job search page first, not in an application form
        try:
            # Check if we need to go back to search results first
            back_button = page.locator('button[aria-label="Back to search results"]')
            if back_button.count() > 0:
                logger.info("Found 'Back to search results' button - clicking it first")
                back_button.click()
                page.wait_for_timeout(6000)  # Wait longer after clicking back
        except Exception as e:
            logger.info(f"No back button found or error checking: {e}")
            
        # Refresh the page to ensure we have fresh content
        logger.info("Refreshing page to ensure fresh content before pagination check")
        page.reload()
        page.wait_for_timeout(10000)  # Increased wait for reload
            
        # Check if pagination container exists
        pagination = page.locator(PAGINATION_CONTAINER_SELECTOR)
        if pagination.count() == 0:
            logger.info("No pagination found. All jobs processed.")
            return True
        
        # Check if there's a "Next" button
        next_button = page.locator(PAGINATION_NEXT_BUTTON_SELECTOR)
        if next_button.count() == 0:
            logger.info("No 'Next' button found. All pages processed.")
            return True
        
        # Log the current page information if available
        page_indicator = page.locator(PAGINATION_PAGE_INDICATOR_SELECTOR)
        if page_indicator.count() > 0:
            page_text = page_indicator.inner_text()
            logger.info(f"Current pagination: {page_text}")
        
        # Store the current URL and also the page number for verification
        current_url = page.url
        current_page_number = None
        if page_indicator.count() > 0:
            try:
                # Try to extract current page number from text like "Page 1 of 4"
                page_text = page_indicator.inner_text()
                match = re.search(r'Page (\d+)', page_text)
                if match:
                    current_page_number = int(match.group(1))
                    logger.info(f"Current page number: {current_page_number}")
            except Exception as e:
                logger.warning(f"Failed to extract page number: {e}")
        
        # Click the Next button
        logger.info("Clicking 'Next' button to navigate to the next page of job results...")
        next_button.click()
        
        # Wait for the page to change
        max_attempts = 5  # Increased from 3 to 5
        for attempt in range(max_attempts):
            try:
                # Wait for URL to change first (indicates navigation started)
                # We'll use a shorter timeout per attempt but more attempts
                page.wait_for_url(lambda url: url != current_url, timeout=8000)
                logger.info("URL changed, checking for job listings...")
                
                # Wait for page to stabilize
                page.wait_for_timeout(8000)
                
                # Check if page number has changed if we know the current page number
                if current_page_number is not None:
                    new_page_indicator = page.locator(PAGINATION_PAGE_INDICATOR_SELECTOR)
                    if new_page_indicator.count() > 0:
                        try:
                            new_page_text = new_page_indicator.inner_text()
                            match = re.search(r'Page (\d+)', new_page_text)
                            if match and int(match.group(1)) > current_page_number:
                                logger.info(f"Page number increased from {current_page_number} to {match.group(1)}")
                                # Success - we've confirmed page has changed
                                page.wait_for_timeout(6000)  # Wait longer for content to load
                                return False
                        except Exception as e:
                            logger.warning(f"Error extracting new page number: {e}")
                
                # Now try to find job listings with various selectors
                selectors = [
                    JOB_LIST_SELECTOR,
                    "ul.jobs-search-results__list", 
                    "div.jobs-search-results-list",
                    "div.jobs-search-results",
                    "section.jobs-search-results-list",
                    "div[data-test-search-results-list]",
                    "div.jobs-search-two-pane__wrapper"  # Another possible container
                ]
                
                # Try each selector
                for selector in selectors:
                    try:
                        logger.info(f"Waiting for job list selector: {selector}")
                        # Shorter timeout per selector but we'll try more selectors
                        element = page.wait_for_selector(selector, timeout=3000, state="visible")
                        if element:
                            logger.info(f"Found job list with selector: {selector}")
                            # Try to verify we have job cards
                            cards = page.locator(f"{selector} li.jobs-search-results__list-item")
                            if cards.count() > 0:
                                logger.info(f"Found {cards.count()} job cards on new page")
                                page.wait_for_timeout(6000)  # Wait longer for content to load
                                return False
                            else:
                                logger.info("List container found but no job cards yet")
                    except PlaywrightError:
                        # Try next selector
                        continue
                
                # If we've tried all selectors without success, reload and try again
                if attempt < max_attempts - 1:  # Don't reload on last attempt
                    logger.warning(f"Attempt {attempt+1}/{max_attempts}: No job list found with any selector. Reloading page...")
                    page.reload()
                    page.wait_for_timeout(10000)  # Give extra time after reload
                else:
                    # On last attempt, just wait longer before giving up
                    logger.warning(f"Attempt {attempt+1}/{max_attempts}: No job list found with any selector. Waiting longer...")
                    page.wait_for_timeout(8000)  # Wait longer on last attempt
            except PlaywrightError as e:
                logger.warning(f"Attempt {attempt+1}/{max_attempts}: Navigation issue: {e}")
                if attempt < max_attempts - 1:  # Don't reload on last attempt
                    logger.info("Reloading page after navigation issue")
                    try:
                        page.reload()
                        page.wait_for_timeout(10000)
                    except Exception as reload_error:
                        logger.warning(f"Error during reload: {reload_error}")
        
        # One last attempt to find at least something on the page
        try:
            # See if we can find ANY jobs section
            any_job_section = page.locator('section.jobs-search-results').first
            if any_job_section:
                logger.info("Found a job section on the page after multiple attempts")
                page.wait_for_timeout(6000)  # Wait longer for content to load
                return False
        except Exception:
            pass
            
        # If we got here, we couldn't confirm successful navigation
        logger.error("Could not verify successful navigation to next page after multiple attempts")
        return True
        
    except PlaywrightError as e:
        logger.error(f"Error navigating to next page: {e}")
        return True  # Treat as if all pages are processed to avoid infinite loops
    except Exception as e:
        logger.error(f"Unexpected error checking pagination: {e}")
        return True
