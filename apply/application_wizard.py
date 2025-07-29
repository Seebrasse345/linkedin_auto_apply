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
    APPLICATION_MODAL_SELECTOR,
    CLOSE_BUTTON_SELECTOR,
    DISCARD_BUTTON_SELECTOR
)
from .helpers import load_answers, save_answers, save_application_result, save_job_description
from .form_processor import FormProcessor
from utils.premium_detector import check_and_handle_premium_redirect
from browser.context import save_cookies_now

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
        """Save application data to JSON files and cookies."""
        # Save successful applications
        for app in self.successful_applications:
            job_data = app.get("job", {})
            job_id = job_data.get("id", "unknown")
            job_id = job_id if job_id != "unknown" else job_data.get("job_id", "unknown")
            
            # Save to successful_applications.json
            self._save_application_result(job_id, True)
            
            # Save job description to job_descriptions_applied.json
            save_job_description(self.data_dir, job_data)
            
        # Save failed applications
        for app in self.failed_applications:
            job_id = app.get("job", {}).get("id", "unknown")
            job_id = job_id if job_id != "unknown" else app.get("job", {}).get("job_id", "unknown")
            self._save_application_result(job_id, False)
        
        # Save cookies after processing applications to preserve session state
        if save_cookies_now():
            logger.info("Saved cookies after processing application data")
        else:
            logger.warning("Failed to save cookies after processing applications")
    
    def _emergency_exit_application(self, reason: str = "Unknown") -> bool:
        """
        Emergency exit procedure to close stuck applications.
        
        Args:
            reason: Reason for the emergency exit
            
        Returns:
            bool: True if successfully exited, False otherwise
        """
        logger.warning(f"Initiating emergency exit procedure: {reason}")
        
        try:
            # Take a debug screenshot before attempting exit
            try:
                debug_dir = os.path.join(self.data_dir, 'debug')
                os.makedirs(debug_dir, exist_ok=True)
                screenshot_path = os.path.join(debug_dir, f"emergency_exit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                self.page.screenshot(path=screenshot_path)
                logger.info(f"Saved emergency exit debug screenshot to {screenshot_path}")
            except Exception as e:
                logger.error(f"Failed to save emergency exit debug screenshot: {e}")
            
            # Step 1: Look for the close (X) button - try multiple strategies
            close_success = False
            
            # Strategy 1: Try the comprehensive close button selector
            try:
                close_button = self.page.locator(CLOSE_BUTTON_SELECTOR)
                if close_button.count() > 0:
                    logger.info("Found close button using comprehensive selector")
                    close_button.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(1500)
                    close_success = True
                else:
                    logger.warning("No close button found with comprehensive selector")
            except Exception as e:
                logger.warning(f"Error with comprehensive close selector: {e}")
            
            # Strategy 2: If first strategy failed, try SVG-specific approach
            if not close_success:
                try:
                    # Look for the specific SVG close icon you mentioned
                    svg_close = self.page.locator('svg[data-test-icon="close-medium"]').first
                    if svg_close.count() > 0:
                        logger.info("Found SVG close icon, clicking parent button")
                        # Click the parent button of the SVG
                        parent_button = svg_close.locator('xpath=ancestor::button[1]')
                        if parent_button.count() > 0:
                            parent_button.click(force=True, timeout=3000)
                            self.page.wait_for_timeout(1500)
                            close_success = True
                        else:
                            # Try clicking the SVG directly
                            svg_close.click(force=True, timeout=3000)
                            self.page.wait_for_timeout(1500)
                            close_success = True
                except Exception as e:
                    logger.warning(f"Error with SVG close approach: {e}")
            
            # Strategy 3: If still failed, try JavaScript approach
            if not close_success:
                try:
                    logger.info("Attempting JavaScript-based close button click")
                    js_result = self.page.evaluate("""
                        () => {
                            // Look for close buttons by multiple criteria
                            const selectors = [
                                'button[aria-label="Dismiss"]',
                                'button[data-test-modal-close-btn]',
                                'button.artdeco-modal__dismiss',
                                'button:has(svg[data-test-icon="close-medium"])',
                                'button.artdeco-button--circle'
                            ];
                            
                            for (const selector of selectors) {
                                try {
                                    const elements = document.querySelectorAll(selector);
                                    if (elements.length > 0) {
                                        elements[0].click();
                                        return `Success with ${selector}`;
                                    }
                                } catch (e) {
                                    console.log(`Failed with ${selector}:`, e);
                                }
                            }
                            
                            // Last resort - look for any button containing close-medium SVG
                            const svgElements = document.querySelectorAll('svg[data-test-icon="close-medium"], use[href="#close-medium"]');
                            if (svgElements.length > 0) {
                                const button = svgElements[0].closest('button');
                                if (button) {
                                    button.click();
                                    return 'Success with SVG parent button';
                                }
                            }
                            
                            return 'No close button found';
                        }
                    """)
                    
                    if "Success" in js_result:
                        logger.info(f"JavaScript close approach succeeded: {js_result}")
                        self.page.wait_for_timeout(1500)
                        close_success = True
                    else:
                        logger.warning(f"JavaScript close approach failed: {js_result}")
                except Exception as e:
                    logger.error(f"Error with JavaScript close approach: {e}")
            
            if not close_success:
                logger.error("Could not find or click close button with any strategy")
                return False
            
            # Step 2: Look for and click the Discard button in the confirmation dialog
            discard_success = False
            
            # Wait a bit more for the discard dialog to appear
            self.page.wait_for_timeout(1000)
            
            # Strategy 1: Try the comprehensive discard button selector
            try:
                    discard_button = self.page.locator(DISCARD_BUTTON_SELECTOR)
                    if discard_button.count() > 0:
                        logger.info("Found discard button using comprehensive selector")
                        discard_button.first.click(force=True, timeout=3000)
                        self.page.wait_for_timeout(1000)
                        
                        # Check for premium page redirect after discard button click
                        if check_and_handle_premium_redirect(self.page):
                            logger.info("Handled premium page redirect after clicking discard button")
                            self.page.wait_for_timeout(1000)
                        
                        discard_success = True
                    else:
                        logger.warning("No discard button found with comprehensive selector")
            except Exception as e:
                    logger.warning(f"Error with comprehensive discard selector: {e}")
            
            # Strategy 2: Try JavaScript approach for discard button
            if not discard_success:
                try:
                    logger.info("Attempting JavaScript-based discard button click")
                    js_result = self.page.evaluate("""
                        () => {
                            // Look for discard buttons by multiple criteria
                            const selectors = [
                                'button[data-control-name="discard_application_confirm_btn"]',
                                'button[data-test-dialog-secondary-btn]',
                                'button.artdeco-modal__confirm-dialog-btn',
                                'button.artdeco-button--secondary'
                            ];
                            
                            for (const selector of selectors) {
                                try {
                                    const elements = document.querySelectorAll(selector);
                                    for (const element of elements) {
                                        const text = element.textContent || element.innerText || '';
                                        if (text.toLowerCase().includes('discard')) {
                                            element.click();
                                            return `Success with ${selector} containing "${text}"`;
                                        }
                                    }
                                } catch (e) {
                                    console.log(`Failed with ${selector}:`, e);
                                }
                            }
                            
                            // Fallback - look for any button with "Discard" text
                            const allButtons = document.querySelectorAll('button');
                            for (const button of allButtons) {
                                const text = button.textContent || button.innerText || '';
                                if (text.toLowerCase().includes('discard')) {
                                    button.click();
                                    return `Success with text-based search: "${text}"`;
                                }
                            }
                            
                            return 'No discard button found';
                        }
                    """)
                    
                    if "Success" in js_result:
                        logger.info(f"JavaScript discard approach succeeded: {js_result}")
                        self.page.wait_for_timeout(1000)
                        
                        # Check for premium page redirect after JavaScript discard button click
                        if check_and_handle_premium_redirect(self.page):
                            logger.info("Handled premium page redirect after JavaScript discard button click")
                            self.page.wait_for_timeout(1000)
                        
                        discard_success = True
                    else:
                        logger.warning(f"JavaScript discard approach failed: {js_result}")
                except Exception as e:
                    logger.error(f"Error with JavaScript discard approach: {e}")
            
            if not discard_success:
                logger.warning("Could not find or click discard button - application may still be partially open")
                # Even without discard, the close button click might have been enough
                
            # Step 3: Verify that we're back to the job listing
            try:
                self.page.wait_for_timeout(2000)  # Wait for any transitions
                # Check if application modal is gone
                modal = self.page.locator(APPLICATION_MODAL_SELECTOR)
                if modal.count() == 0:
                    logger.info("Emergency exit successful - application modal is gone")
                    return True
                else:
                    logger.warning("Emergency exit may have failed - application modal still present")
                    return False
            except Exception as e:
                logger.error(f"Error verifying emergency exit success: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Critical error during emergency exit procedure: {e}")
            return False
    
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
            max_steps = 8  # Safety limit
            previous_form_content = None  # Track previous form content to detect loops
            duplicate_form_count = 0  # Count how many times we see the same form
            max_duplicates = 2  # Reduced from 3 to 2 for faster failure detection
            stuck_detection_count = 0  # Additional counter for detecting stuck situations
            max_stuck_attempts = 5  # Maximum attempts before considering the application stuck
            
            # Initialize the form processor
            form_processor = FormProcessor(self.page, self.answers)

            while step_count < max_steps:
                logger.info(f"Processing application step {step_count + 1}")

                # Check for premium page redirect at the start of each step
                if check_and_handle_premium_redirect(self.page):
                    logger.info(f"Handled premium page redirect during application step {step_count + 1}")
                    self.page.wait_for_timeout(1000)

                # Locate the application modal
                modal = self.page.locator(APPLICATION_MODAL_SELECTOR)
                if modal.count() == 0:
                    logger.warning("Application modal not found during navigation")
                    
                    # Modal disappeared - this usually means we're stuck or there was an error
                    # Try emergency exit to ensure we're back to a clean state
                    exit_success = self._emergency_exit_application(f"Application modal disappeared at step {step_count + 1}")
                    
                    self.failed_applications.append({
                        "job": job_data,
                        "reason": f"Application modal disappeared at step {step_count + 1}, emergency exit {'successful' if exit_success else 'failed'}",
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
                            # Use our comprehensive emergency exit procedure
                            exit_success = self._emergency_exit_application(f"Infinite loop detected at step {step_count + 1}")
                            
                            self.failed_applications.append({
                                "job": job_data,
                                "reason": f"Infinite loop detected in application form at step {step_count + 1}, emergency exit {'successful' if exit_success else 'failed'}",
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_FAILURE
                else:
                    # Reset the counter if form content changed
                    duplicate_form_count = 0
                    previous_form_content = current_form_content

                # Store the current job data in answers for use in cover letter generation
                self.answers['current_job_data'] = job_data
                
                # Process form fields on current step
                form_processor = FormProcessor(self.page, self.answers, job_data)
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
                            
                            # Use emergency exit procedure since we're stuck after submission
                            exit_success = self._emergency_exit_application("No Done button found after submission")
                            
                            self.failed_applications.append({
                                "job": job_data,
                                "reason": f"No Done button after submission, emergency exit {'successful' if exit_success else 'failed'}",
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_FAILURE
                    except PlaywrightError as e:
                        logger.error(f"Error clicking Submit button: {e}")
                        
                        # Use emergency exit procedure since submit failed
                        exit_success = self._emergency_exit_application(f"Submit button click failed: {e}")
                        
                        self.failed_applications.append({
                            "job": job_data,
                            "reason": f"Error clicking Submit button: {e}, emergency exit {'successful' if exit_success else 'failed'}",
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
                        
                        # Check for premium page redirect after clicking next button
                        if check_and_handle_premium_redirect(self.page):
                            logger.info(f"Handled premium page redirect after clicking official next button")
                            self.page.wait_for_timeout(1000)
                        
                        step_count += 1
                        stuck_detection_count = 0  # Reset stuck counter on successful navigation
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking official next button: {e}, will try alternatives")
                        stuck_detection_count += 1

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
                        
                        # Check for premium page redirect after clicking footer next button
                        if check_and_handle_premium_redirect(self.page):
                            logger.info(f"Handled premium page redirect after clicking footer next button")
                            self.page.wait_for_timeout(1000)
                        
                        step_count += 1
                        stuck_detection_count = 0  # Reset stuck counter on successful navigation
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking Next button: {e}. Trying alternatives")
                        stuck_detection_count += 1

                # Try finding a button with "Continue to next step" aria-label (LinkedIn specific)
                next_button = app_modal.locator("button[aria-label='Continue to next step']")
                if next_button.count() > 0:
                    logger.info("Found Next button with 'Continue to next step' aria-label")
                    try:
                        next_button.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        stuck_detection_count = 0  # Reset stuck counter on successful navigation
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking aria-label Next button: {e}. Trying alternatives")
                        stuck_detection_count += 1

                # Try finding a button with "Review your application" aria-label (LinkedIn specific)
                review_button = app_modal.locator("button[aria-label='Review your application'], button:has-text('Review')")
                if review_button.count() > 0:
                    logger.info("Found Review button - clicking it to move to final step")
                    try:
                        # Try multiple click strategies for reliability
                        try:
                            # First try regular click
                            review_button.first.click(force=True,timeout=3000)
                        except PlaywrightError:
                            # Fall back to JavaScript click
                            review_button.first.evaluate("button => button.click()")
                            
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        stuck_detection_count = 0  # Reset stuck counter on successful navigation
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking Review button: {e}. Will try other approaches.")
                        stuck_detection_count += 1
                        
                # Finally, try a more general approach - any button with text "Next"
                next_text_button = app_modal.locator("button:has-text('Next')")
                if next_text_button.count() > 0:
                    logger.info("Found button with text 'Next'")
                    try:
                        next_text_button.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        stuck_detection_count = 0  # Reset stuck counter on successful navigation
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking text Next button: {e}. Trying one last approach")
                        stuck_detection_count += 1
                    
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
                            stuck_detection_count = 0  # Reset stuck counter on successful navigation
                            continue
                    except PlaywrightError as e:
                        logger.error(f"Error clicking potential Next button: {e}")
                        stuck_detection_count += 1
                
                # Check if we're stuck based on failed attempts
                if stuck_detection_count >= max_stuck_attempts:
                    logger.error(f"Application appears stuck after {stuck_detection_count} failed attempts to navigate")
                    # Use emergency exit procedure for stuck applications
                    exit_success = self._emergency_exit_application(f"Application stuck after {stuck_detection_count} failed navigation attempts")
                    
                    self.failed_applications.append({
                        "job": job_data,
                        "reason": f"Application stuck after {stuck_detection_count} failed navigation attempts, emergency exit {'successful' if exit_success else 'failed'}",
                        "timestamp": datetime.now().isoformat()
                    })
                    self._save_application_data()
                    return APPLICATION_FAILURE
                
                # If we get here, we couldn't find a working next button
                logger.warning(f"Could not find a working Next button on step {step_count + 1}")
                
                # Use emergency exit procedure for stuck applications
                exit_success = self._emergency_exit_application(f"No working Next button found on step {step_count + 1}")
                
                self.failed_applications.append({
                    "job": job_data,
                    "reason": f"No working Next button found on step {step_count + 1}, emergency exit {'successful' if exit_success else 'failed'}",
                    "timestamp": datetime.now().isoformat()
                })
                self._save_application_data()
                return APPLICATION_FAILURE

            # If we reach max steps without finding a Submit button
            logger.warning(f"Reached maximum step count ({max_steps}) without completing application")
            
            # Use emergency exit procedure for stuck applications
            exit_success = self._emergency_exit_application(f"Reached max step count ({max_steps}) without completion")
            
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Reached max step count ({max_steps}) without Submit button, emergency exit {'successful' if exit_success else 'failed'}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE

        except TimeoutError as e:
            logger.error(f"Timeout during application process: {e}")
            
            # Use emergency exit procedure to ensure clean state after timeout
            exit_success = self._emergency_exit_application(f"Timeout occurred: {e}")
            
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Timeout: {e}, emergency exit {'successful' if exit_success else 'failed'}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE
        except PlaywrightError as e:
            logger.error(f"Playwright error during application process: {e}")
            
            # Use emergency exit procedure to ensure clean state after playwright error
            exit_success = self._emergency_exit_application(f"Playwright error occurred: {e}")
            
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Playwright error: {e}, emergency exit {'successful' if exit_success else 'failed'}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE
        except Exception as e:
            logger.error(f"Unexpected error during application process: {e}")
            
            # Use emergency exit procedure to ensure clean state after unexpected error
            exit_success = self._emergency_exit_application(f"Unexpected error occurred: {e}")
            
            self.failed_applications.append({
                "job": job_data,
                "reason": f"Unexpected error: {e}, emergency exit {'successful' if exit_success else 'failed'}",
                "timestamp": datetime.now().isoformat()
            })
            self._save_application_data()
            return APPLICATION_FAILURE
