import logging
import time
import random
import re
from playwright.sync_api import Page, Locator, Error as PlaywrightError
from typing import List, Dict, Set, Optional
from apply.wizard import ApplicationWizard, APPLICATION_SUCCESS, APPLICATION_FAILURE, APPLICATION_INCOMPLETE

logger = logging.getLogger(__name__)

# Selectors (Adjust based on LinkedIn structure)
SCROLL_CONTAINER_SELECTOR = "div.jobs-search-results-list" # Updated selector for the scrollable job list container
JOB_CARD_SELECTOR = "li.scaffold-layout__list-item" # The list item containing the card
# Combine potential selectors, Playwright takes the first match
JOB_LINK_SELECTOR = "a.job-card-container__link, a.job-card-list__title" 
JOB_TITLE_SELECTOR = f"{JOB_LINK_SELECTOR} strong" # Title often within strong tag inside the link
# Separate company selectors for sequential fallback
JOB_COMPANY_SELECTOR_PRIMARY = "span.job-card-container__primary-description"
JOB_COMPANY_SELECTOR_SECONDARY = "a.job-card-container__company-name" 

# Default settings
SCROLL_INCREMENT = 3  # Scroll every Nth card (increased for faster scrolling)
MAX_SCROLL_ATTEMPTS = 20 # Max scroll attempts to prevent infinite loops (reduced from 30)
SCROLL_STABILITY_CHECKS = 2 # Stop if DOM count is stable for this many checks (reduced from 3)
POST_SCROLL_DELAY_MS = 800 # Delay after each scroll_into_view (reduced from 1200ms)
EXTRACT_TIMEOUT_MS = 3000 # Timeout for extracting text/attributes from elements (reduced from 5000ms)
QUICK_EXTRACT_TIMEOUT_MS = 1000 # Faster timeout for individual fields (reduced from 2000ms)
INITIAL_WAIT_MS = 1500 # Wait briefly for initial cards to appear (reduced from 2000ms)

# --- Selectors --- 
# For the Job List Items (Scrolling & Clicking)
DETAILS_PANE_TITLE_SELECTOR = ".job-details-jobs-unified-top-card__job-title"
DETAILS_PANE_COMPANY_SELECTOR = ".job-details-jobs-unified-top-card__company-name a" # Link inside company name
DETAILS_PANE_LOCATION_SELECTOR = ".job-details-jobs-unified-top-card__primary-description-without-tagline span.job-details-jobs-unified-top-card__bullet" # Location often uses bullets
DETAILS_PANE_DESCRIPTION_SELECTOR = ".jobs-description-content__text"
DETAILS_PANE_EASY_APPLY_BUTTON_SELECTOR = 'button.jobs-apply-button span.artdeco-button__text'
DETAILS_PANE_APPLY_BUTTON_SELECTOR = 'button.jobs-apply-button'

# --- Settings --- 
POST_CLICK_DELAY_MS = 1000 # Wait after clicking a card for pane to load (reduced from 1500ms)

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

def load_all_job_cards(page: Page) -> List[Dict[str, str]]:
    """Loads job cards via scrolling, then clicks each card to extract details from the main pane.

    1. Determines initial max number of job card elements in DOM.
    2. Scrolls cards at indices (0, SCROLL_INCREMENT, ...) up to that max count into view.
    3. Iterates through located cards, clicks each, waits for details pane, extracts.

    Args:
        page: The Playwright Page object.

    Returns:
        A list of dictionaries containing details of unique job cards found.
    """
    job_data_list: List[Dict[str, str]] = []
    seen_job_ids: Set[str] = set()

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
                try:
                    desc_elem = page.locator(DETAILS_PANE_DESCRIPTION_SELECTOR).first
                    job_description = desc_elem.inner_text(timeout=EXTRACT_TIMEOUT_MS).strip()
                except Exception as e:
                    pass # Suppress warning as requested
                
                # 5. Store data
                job_details = {
                    'job_id': job_id,
                    'title': job_title,
                    'company': company_name,
                    'location': location,
                    'posted_date': 'N/A', # Not easily available in details pane usually
                    'url': job_url, # URL when detail pane is visible
                    'easy_apply': is_easy_apply,
                    'description': job_description[:200] + '...' if len(job_description) > 200 else job_description # Truncate description
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

        logger.info(f"Extraction phase complete. Processed {processed_count}/{final_card_count} cards found, added {added_count} unique jobs.")

    except Exception as e_extract_phase:
        logger.error(f"Error during the final extraction phase: {e_extract_phase}")
        return job_data_list # Return whatever was collected before the error

    return job_data_list
