"""
ApplicationWizard class for handling the LinkedIn job application process.
Coordinates the application flow and form interaction.
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from playwright.sync_api import Page, TimeoutError, Error as PlaywrightError

from .constants import (
    APPLICATION_SUCCESS,
    APPLICATION_FAILURE,
    APPLICATION_INCOMPLETE,
    EASY_APPLY_BUTTON_SELECTOR,
    NEXT_BUTTON_SELECTOR,
    SUBMIT_BUTTON_SELECTOR,
    DONE_BUTTON_SELECTOR,
    APPLICATION_MODAL_SELECTOR
)
from .helpers import load_answers, save_answers, save_application_result
from .form_processor import FormProcessor

logger = logging.getLogger(__name__)

class ApplicationWizard:
    """Handles the LinkedIn job application process."""
    
    def __init__(self, page: Page, answers_file: str = 'answers/default.json'):
        """Initialize the application wizard.
        
        Args:
            page: Playwright page
            answers_file: Path to the answers JSON file
        """
        self.page = page
        self.answers_file = answers_file
        self.successful_applications = []
        self.failed_applications = []
        self.answers = load_answers(answers_file)
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _save_answers(self) -> None:
        """Save updated answers back to the JSON file."""
        save_answers(self.answers_file, self.answers)
    
    def _save_application_result(self, job_id: str, success: bool) -> None:
        """Save application result to a JSON file. Concatenates with existing results."""
        save_application_result(self.data_dir, job_id, success)
    
    def _save_application_data(self) -> None:
        """Save application data to JSON files."""
        # Save successful applications
        for app in self.successful_applications:
            job_id = app.get("job", {}).get("id", "unknown")
            job_id = job_id if job_id != "unknown" else app.get("job", {}).get("job_id", "unknown")
            self._save_application_result(job_id, True)
            
        # Save failed applications
        for app in self.failed_applications:
            job_id = app.get("job", {}).get("id", "unknown")
            job_id = job_id if job_id != "unknown" else app.get("job", {}).get("job_id", "unknown")
            self._save_application_result(job_id, False)
    
    def start_application(self, job_data: Dict[str, str]) -> str:
        """Start the application process for a job.
        
        Args:
            job_data: Dictionary containing job information
            
        Returns:
            str: Application status (success, failure, incomplete)
        """
        logger.info(f"Starting application for job: {job_data.get('title', 'Unknown')}")

        try:
            # Check if job_data contains a flag indicating the Easy Apply button was already clicked
            if job_data.get('easy_apply_clicked', False):
                logger.info("Easy Apply button was already clicked, proceeding with application")
                # No need to click again, just wait for the form to load
                self.page.wait_for_timeout(1000)            
            else:
                # Check if we can find an Easy Apply button
                easy_apply_button = self.page.locator(EASY_APPLY_BUTTON_SELECTOR)
                if easy_apply_button.count() == 0:
                    logger.warning("No Easy Apply button found")
                    self.failed_applications.append({
                        "job": job_data,
                        "reason": "No Easy Apply button found",
                        "timestamp": datetime.now().isoformat()
                    })
                    return APPLICATION_FAILURE

                # Click the Easy Apply button (use first() to handle multiple matches)
                logger.info("Clicking Easy Apply button")
                easy_apply_button.first.click()
                self.page.wait_for_timeout(1500)  # Wait for the form to load (reduced from 2000ms)

            # Process the application form steps
            step_count = 0
            max_steps = 15  # Safety limit
            previous_form_content = None  # Track previous form content to detect loops
            duplicate_form_count = 0  # Count how many times we see the same form
            max_duplicates = 3  # Maximum number of times to try the same form before giving up
            
            # Initialize the form processor
            form_processor = FormProcessor(self.page, self.answers)

            while step_count < max_steps:
                logger.info(f"Processing application step {step_count + 1}")

                # Locate the application modal
                modal = self.page.locator(APPLICATION_MODAL_SELECTOR)
                if modal.count() == 0:
                    logger.warning("Application modal not found during navigation")
                    self.failed_applications.append({
                        "job": job_data,
                        "reason": f"Application modal disappeared at step {step_count + 1}",
                        "timestamp": datetime.now().isoformat()
                    })
                    self._save_application_data()
                    return APPLICATION_FAILURE

                app_modal = modal.first

                # Check if we're in a loop by comparing form content with previous step
                current_form_content = app_modal.inner_html()
                if current_form_content == previous_form_content:
                    duplicate_form_count += 1
                    logger.warning(f"Detected same form content in consecutive steps ({duplicate_form_count}/{max_duplicates})")
                    
                    if duplicate_form_count >= max_duplicates:
                        logger.error(f"Detected infinite loop in application form - same form appeared {max_duplicates} times")

                        # Try a different approach - click a different next button if available
                        all_buttons = app_modal.locator("button")
                        found_alternative = False

                        for i in range(all_buttons.count()):
                            button = all_buttons.nth(i)
                            button_text = button.inner_text().lower()
                            if any(word in button_text for word in ["next", "continue", "submit", "review"]):
                                if i > 0:  # Not the first button we've been clicking
                                    logger.info(f"Trying alternative button with text: {button_text}")
                                    button.click()
                                    self.page.wait_for_timeout(2000)
                                    found_alternative = True
                                    break

                        if not found_alternative:
                            # Take a debug screenshot
                            try:
                                debug_dir = os.path.join(self.data_dir, 'debug')
                                os.makedirs(debug_dir, exist_ok=True)
                                screenshot_path = os.path.join(debug_dir, f"form_loop_{step_count+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                                self.page.screenshot(path=screenshot_path)
                                logger.info(f"Saved debug screenshot to {screenshot_path}")
                            except Exception as e:
                                logger.error(f"Failed to save debug screenshot: {e}")
                                
                            self.failed_applications.append({
                                "job": job_data,
                                "reason": f"Infinite loop detected in application form at step {step_count + 1}",
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_FAILURE
                else:
                    # Reset the counter if form content changed
                    duplicate_form_count = 0
                    previous_form_content = current_form_content

                # Process form fields on current step
                form_processor = FormProcessor(self.page, self.answers)
                form_success = form_processor.process_form_fields()
                
                # Save answers immediately after processing each form
                self._save_answers()
                
                if not form_success:
                    logger.warning(f"Some fields failed to process in step {step_count+1}")

                self.page.wait_for_timeout(800)  # Wait for fields to be filled (reduced from 1000ms)

                # Check for Submit button within the modal
                submit_button = app_modal.locator(SUBMIT_BUTTON_SELECTOR)
                review_button = app_modal.locator("button[aria-label='Review your application'], button:has-text('Review')") 
                
                # First check for submit button
                if submit_button.count() > 0:
                    logger.info("Found Submit button - this is the final step")
                    try:
                        # Try multiple click strategies for better reliability
                        logger.info("Attempting to click Submit button...")
                        submit_success = False
                        
                        # First try direct click which sometimes works better
                        try:
                            submit_button.first.click(timeout=3000)
                            submit_success = True
                            logger.info("Successfully clicked Submit button directly")
                        except PlaywrightError as click_e:
                            logger.warning(f"Direct click on Submit button failed: {click_e}. Trying JavaScript click.")
                            
                        # Then try JavaScript click if direct didn't work
                        if not submit_success:
                            try:
                                submit_button.first.evaluate("button => button.click()")
                                submit_success = True
                                logger.info("Successfully clicked Submit button via JavaScript")
                            except PlaywrightError as js_e:
                                logger.error(f"JavaScript click on Submit button failed: {js_e}. Will try force click.")
                        
                        # Last resort: try force click with JavaScript on the most reliable selector
                        if not submit_success:
                            try:
                                self.page.evaluate("""
                                    (() => {
                                        const submitButtons = document.querySelectorAll('button[aria-label="Submit application"], button:has-text("Submit application")');
                                        if (submitButtons && submitButtons.length > 0) {
                                            submitButtons[0].click();
                                            return true;
                                        }
                                        return false;
                                    })()
                                """)
                                logger.info("Attempted force click on Submit button via page-level JavaScript")
                            except PlaywrightError as force_e:
                                logger.error(f"Force click on Submit button failed: {force_e}")
                                
                        self.page.wait_for_timeout(2000)  # Longer wait for submission to process

                        # Check for Done button - may be in a new modal (check both in modal and whole page)
                        # First check in current modal if it still exists
                        if modal.count() > 0:
                            done_in_modal = app_modal.locator(DONE_BUTTON_SELECTOR)
                            if done_in_modal.count() > 0:
                                logger.info("Found Done button in current modal - application completed successfully")
                                done_in_modal.first.evaluate("button => button.click()")
                                self.page.wait_for_timeout(1000)

                                # Record successful application
                                self.successful_applications.append({
                                    "job": job_data,
                                    "timestamp": datetime.now().isoformat()
                                })
                                self._save_application_data()
                                return APPLICATION_SUCCESS

                        # If not found in modal, check whole page (may be in a different modal)
                        done_button = self.page.locator(DONE_BUTTON_SELECTOR)
                        if done_button.count() > 0:
                            logger.info("Found Done button in new modal - application completed successfully")
                            done_button.first.evaluate("button => button.click()")
                            self.page.wait_for_timeout(1000)

                            # Record successful application
                            self.successful_applications.append({
                                "job": job_data,
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_SUCCESS
                        else:
                            logger.warning("Did not find Done button after submission")
                            self.failed_applications.append({
                                "job": job_data,
                                "reason": "No Done button after submission",
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_FAILURE
                    except PlaywrightError as e:
                        logger.error(f"Error clicking Submit button: {e}")
                        self.failed_applications.append({
                            "job": job_data,
                            "reason": f"Error clicking Submit button: {e}",
                            "timestamp": datetime.now().isoformat()
                        })
                        self._save_application_data()
                        return APPLICATION_FAILURE

                # Debug: Output all button text for analysis
                all_form_buttons = app_modal.locator("button")
                logger.info(f"Found {all_form_buttons.count()} total buttons in the form")
                for i in range(min(all_form_buttons.count(), 5)):  # Limit to first 5 to avoid spam
                    try:
                        button = all_form_buttons.nth(i)
                        button_text = button.inner_text().strip()
                        button_attrs = {}
                        for attr in ['aria-label', 'id', 'data-easy-apply-next-button', 'class']:
                            value = button.get_attribute(attr)
                            if value:
                                button_attrs[attr] = value
                        logger.info(f"Button {i+1} text: '{button_text}', attributes: {button_attrs}")
                    except PlaywrightError:
                        pass
                
                # First try the most specific button - data-easy-apply-next-button (this is the official LinkedIn attribute)
                next_with_attr = app_modal.locator("[data-easy-apply-next-button]")
                logger.info(f"Found {next_with_attr.count()} buttons with data-easy-apply-next-button attribute")
                if next_with_attr.count() > 0:
                    logger.info("Using official LinkedIn next button with data-easy-apply-next-button attribute")
                    try:
                        next_with_attr.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking official next button: {e}, will try alternatives")

                # Then try to find the specific footer Next button
                footer_next = app_modal.locator("footer button:has-text('Next')")
                logger.info(f"Found {footer_next.count()} footer Next buttons")
                if footer_next.count() > 0:
                    # This is the most reliable button - in the footer of the form
                    logger.info("Found Next button in form footer - clicking it")
                    try:
                        # Use evaluate to force a click (more reliable than regular click)
                        footer_next.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking Next button: {e}. Trying alternatives")

                # Try finding a button with "Continue to next step" aria-label (LinkedIn specific)
                next_button = app_modal.locator("button[aria-label='Continue to next step']")
                if next_button.count() > 0:
                    logger.info("Found Next button with 'Continue to next step' aria-label")
                    try:
                        next_button.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking aria-label Next button: {e}. Trying alternatives")

                # Try finding a button with "Review your application" aria-label (LinkedIn specific)
                review_button = app_modal.locator("button[aria-label='Review your application'], button:has-text('Review')")
                if review_button.count() > 0:
                    logger.info("Found Review button - clicking it to move to final step")
                    try:
                        # Try multiple click strategies for reliability
                        try:
                            # First try regular click
                            review_button.first.click(timeout=3000)
                        except PlaywrightError:
                            # Fall back to JavaScript click
                            review_button.first.evaluate("button => button.click()")
                            
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking Review button: {e}. Will try other approaches.")
                        
                # Finally, try a more general approach - any button with text "Next"
                next_text_button = app_modal.locator("button:has-text('Next')")
                if next_text_button.count() > 0:
                    logger.info("Found button with text 'Next'")
                    try:
                        next_text_button.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking text Next button: {e}. Trying one last approach")
                    
                # Last resort - try to find any button that might be a next button by examining common CSS classes
                # This is very specific to LinkedIn but helps with some edge cases
                potential_next = app_modal.locator("button.artdeco-button--primary, button.artdeco-button--secondary")
                if potential_next.count() > 0:
                    # Try clicking the last one (usually the action button is at the end)
                    try:
                        last_button = potential_next.nth(potential_next.count() - 1)
                        button_text = last_button.inner_text().strip().lower()
                        
                        # Only click if it looks like a navigation button
                        if any(word in button_text for word in ["next", "continue", "proceed", "submit", "review"]):
                            logger.info(f"Trying potential Next button with text: {button_text}")
                            last_button.evaluate("button => button.click()")
                            self.page.wait_for_timeout(1500)  # Wait for next step to load
                            step_count += 1
                            continue
                    except PlaywrightError as e:
                        logger.error(f"Error clicking potential Next button: {e}")
                
                # If we get here, we couldn't find a working next button
                logger.warning(f"Could not find a working Next button on step {step_count + 1}")
                self.failed_applications.append({
                    "job": job_data,
                    "reason": f"No working Next button found on step {step_count + 1}",
                    "timestamp": datetime.now().isoformat()
                })
                self._save_application_data()
                return APPLICATION_INCOMPLETE

            # If we reach max steps without finding a Submit button
            logger.warning(f"Reached maximum step count ({max_steps}) without completing application")
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Reached max step count ({max_steps}) without Submit button",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_INCOMPLETE

        except TimeoutError as e:
            logger.error(f"Timeout during application process: {e}")
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Timeout: {e}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE
        except PlaywrightError as e:
            logger.error(f"Playwright error during application process: {e}")
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Playwright error: {e}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE
        except Exception as e:
            logger.error(f"Unexpected error during application process: {e}")
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Unexpected error: {e}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE
