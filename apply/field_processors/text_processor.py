"""
Text input and textarea field processors for LinkedIn job application forms.
"""
import logging
import os
import time
from typing import Dict, Any, Optional
from playwright.sync_api import Locator, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from .base import FieldProcessor
from ..helpers import get_answer_for_field, save_answers
from ..cover_letter_generator import generate_cover_letter

logger = logging.getLogger(__name__)

class TextInputProcessor(FieldProcessor):
    """Processor for text input fields."""
    
    def __init__(self):
        """Initialize the processor."""
        super().__init__()
    
    def process(self, input_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a text input field.
        
        Args:
            input_element: Playwright locator for the text input element
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        field_label = self.get_field_label(input_element)
        input_id = input_element.get_attribute("id")

        # Check for the specific Home Address City field
        # The ID "single-typeahead-entity-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-4170832850-7558611383530654713-city-HOME-CITY"
        # is too specific and might change. We look for a more general part.
        if input_id and "city-HOME-CITY" in input_id and field_label.lower() == "city":
            try:
                logger.info(f"Attempting to fill Home Address City field ('{field_label}') with 'Sheffield, England, United Kingdom' by selecting suggestion.")
                input_element.click() # Ensure focus
                input_element.fill("") # Explicitly clear the field first
                
                logger.info("Typing 'Sheffield' into Home Address City field to trigger autocomplete...")
                # Type only 'Sheffield' to trigger suggestions, with a slight delay for each character
                input_element.type("Sheffield", delay=75) 
                
                suggestion_text = "Sheffield, England, United Kingdom"
                suggestion_element = None
                
                # Common CSS selectors for autocomplete suggestions. These are tried in order.
                suggestion_locator_css_options = [
                    f'li[role="option"]:has-text("{suggestion_text}")',
                    f'div[role="option"]:has-text("{suggestion_text}")',
                    f'p:has-text("{suggestion_text}")',
                    f'span:has-text("{suggestion_text}")',
                    f'*[role="listbox"] li:has-text("{suggestion_text}")',
                    f'*[role="listbox"] div:has-text("{suggestion_text}")',
                    f':text-matches("^{suggestion_text}$")' # Playwright specific :text-matches for exact match
                ]

                # Iterate through selectors to find the suggestion element
                for i, css_selector in enumerate(suggestion_locator_css_options):
                    try:
                        logger.debug(f"Home Address City: Trying suggestion selector {i+1}/{len(suggestion_locator_css_options)}: {css_selector}")
                        # Scope locator to the page, as dropdowns might not be direct children or could be in portals
                        located_element = input_element.page.locator(css_selector).first
                        # Wait for the element to be visible, with a timeout for each attempt
                        located_element.wait_for(state="visible", timeout=1500) # 1.5 sec timeout for each selector
                        suggestion_element = located_element
                        logger.info(f"Home Address City: Suggestion '{suggestion_text}' found and visible with: {css_selector}")
                        break 
                    except PlaywrightTimeoutError:
                        logger.debug(f"Home Address City: Timeout waiting for suggestion with selector: {css_selector}")
                    except Exception as e_loc_suggestion:
                        logger.warning(f"Home Address City: Error with selector {css_selector}: {str(e_loc_suggestion)[:100]}") # Log snippet of error
                
                if suggestion_element:
                    logger.info(f"Home Address City: Clicking suggestion '{suggestion_text}'.")
                    suggestion_element.click()
                    input_element.page.wait_for_timeout(750) # Wait for click to process and field to update
                else:
                    logger.warning(f"Home Address City: Suggestion '{suggestion_text}' not found or not visible after trying all selectors. Falling back to direct fill.")
                    input_element.fill("Sheffield, England, United Kingdom") # Fallback to direct fill
                    input_element.page.wait_for_timeout(500)

                current_value = input_element.input_value()
                logger.info(f"Home Address City: Value in field before pressing Enter: '{current_value}'")

                # It might be necessary to ensure focus is back on the input field if the click shifted it
                input_element.focus()
                input_element.press("Enter")
                logger.info("Home Address City: Pressed Enter after handling the field.")
                return True
            except PlaywrightError as e_pe:
                logger.error(f"Home Address City: PlaywrightError encountered: {e_pe}")
                # Attempt a simpler fill as a last resort if the primary method fails catastrophically
                try:
                    logger.info("Home Address City: Fallback - Attempting simple fill due to PlaywrightError.")
                    input_element.fill("Sheffield, England, United Kingdom")
                    input_element.page.wait_for_timeout(300)
                    input_element.press("Enter")
                    logger.info("Home Address City: Fallback - Pressed Enter after simple fill.")
                    return True
                except Exception as e_ff:
                    logger.error(f"Home Address City: Fallback fill also failed: {e_ff}")
                    return False
            except Exception as e_gen:
                logger.error(f"Home Address City: Unexpected error encountered: {e_gen}")
                return False

        answer = get_answer_for_field(answers, field_label)
        
        # Special handling for years of experience questions in text fields
        field_lower = field_label.lower()
        if not answer and ('years of experience' in field_lower or 'years of work experience' in field_lower 
                or 'how many years' in field_lower):
            logger.info(f"Auto-filling years of experience text field: '{field_label}' with '2'")
            answer = "2"
        elif not answer and ("notice period" in field_lower):
            logger.info(f"Auto-filling notice period text field: '{field_label}' with '2'")
            answer = "0"
        elif not answer and ("salary" in field_lower):
            logger.info(f"Auto-filling salary text field: '{field_label}' with '30000'")
            answer = "30000"
        elif not answer:
            answer = self.ask_for_input(field_label, "text", answers)
        
        # Save answer for future use
        answers[field_label] = answer
        
        # Immediately save to disk
        try:
            answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
            save_answers(answers_file, answers)
            logger.info(f"Saved new answer for '{field_label}' immediately to disk")
        except Exception as e:
            logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
        
        try:
            # Special handling for cover letter fields
            if 'cover letter' in field_label.lower():
                logger.info(f"Cover letter field detected: '{field_label}'")
                print(f"\n[APPLICATION FORM] Cover letter field detected. Generating custom cover letter for {self.job_data.get('title', 'this job')} at {self.job_data.get('company', 'this company')}...")
                
                # Check if we need to generate a cover letter
                if answer == '@file:cover_letter.pdf' or not answer:
                    # Wait a moment to simulate cover letter generation (gives user visual feedback)
                    time.sleep(1)
                    
                    # Get job data - first try from this processor, then from answers as fallback
                    effective_job_data = self.job_data
                    if not effective_job_data and 'current_job_data' in answers:
                        effective_job_data = answers['current_job_data']
                    
                    # Generate the custom cover letter
                    if effective_job_data:
                        try:
                            # Generate customized cover letter
                            custom_cover_letter = generate_cover_letter(effective_job_data, answers)
                            logger.info(f"Successfully generated custom cover letter for job at {effective_job_data.get('company', 'Unknown')}")
                            print(f"\n[APPLICATION FORM] Custom cover letter generated successfully!")
                            
                            # Use the generated cover letter
                            input_element.fill(custom_cover_letter)
                            logger.info(f"Filled cover letter field with custom generated content")
                            
                            # Store that we used a generated cover letter
                            answers['used_cover'] = True
                            return True
                        except Exception as e:
                            logger.error(f"Error generating cover letter: {e}")
                            print(f"\n[APPLICATION FORM] Error generating cover letter. Using stored answer instead.")
                    else:
                        logger.warning("Cannot generate cover letter: No job data available")
                        print(f"\n[APPLICATION FORM] Cannot generate cover letter: No job data available. Using stored answer instead.")
                        # Proceed with normal text filling
            
            # Standard field filling
            input_element.fill(answer)
            logger.info(f"Filled text input '{field_label}' with answer")
            return True
        except PlaywrightError as e:
            logger.error(f"Error filling text input '{field_label}': {e}")
            return False


class TextareaProcessor(FieldProcessor):
    """Processor for textarea fields."""
    
    def __init__(self):
        """Initialize the processor."""
        super().__init__()
    
    def process(self, textarea_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a textarea field.
        
        Args:
            textarea_element: Playwright locator for the textarea element
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        field_label = self.get_field_label(textarea_element)
        logger.info(f"Processing textarea field: '{field_label}'")
        answer = get_answer_for_field(answers, field_label)
        
        if not answer:
            answer = self.ask_for_input(field_label, "textarea", answers)
        
        # Save answer for future use
        answers[field_label] = answer
        
        # Immediately save to disk
        try:
            answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
            save_answers(answers_file, answers)
            logger.info(f"Saved new answer for '{field_label}' immediately to disk")
        except Exception as e:
            logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
        
        try:
            # Special handling for cover letter fields - match exactly for 'Cover letter' and several variations
            field_lower = field_label.lower()
            if field_lower == 'cover letter' or 'cover letter' in field_lower:
                logger.info(f"Cover letter field detected in textarea: '{field_label}'")
                # Clear any existing answer - we don't want to use stored answers for cover letters
                answer = ""
                logger.info("Clearing stored answer for cover letter field to force generation of a new one")
                print(f"\n[APPLICATION FORM] Cover letter field detected! Generating fresh cover letter...")
                
                # Always generate the cover letter for these fields, regardless of stored answer
                # Force generation for exact 'Cover letter' fields
                # Wait a moment to simulate cover letter generation (gives user visual feedback)
                time.sleep(1)
                
                # Get job data - first try from this processor, then from answers as fallback
                effective_job_data = None
                
                # First check if self.job_data exists and has content
                if hasattr(self, 'job_data') and self.job_data:
                    effective_job_data = self.job_data
                    logger.info("Using self.job_data for cover letter generation")
                
                # Fallback to current_job_data in answers
                if not effective_job_data and 'current_job_data' in answers:
                    effective_job_data = answers['current_job_data']
                    logger.info("Using answers['current_job_data'] for cover letter generation")
                
                # Debug log with more detailed info
                logger.info(f"Job data for cover letter: ID={effective_job_data.get('job_id', 'Unknown')}, Title={effective_job_data.get('title', 'Unknown')}, Company={effective_job_data.get('company', 'Unknown')}")
                
                # Generate the custom cover letter
                if effective_job_data:
                    try:
                        # Generate customized cover letter
                        print(f"\n[APPLICATION FORM] Generating custom cover letter using OpenAI for {effective_job_data.get('title', 'this job')} at {effective_job_data.get('company', 'this company')}...")
                        custom_cover_letter = generate_cover_letter(effective_job_data, answers)
                        logger.info(f"Successfully generated custom cover letter for job at {effective_job_data.get('company', 'Unknown')}")
                        print(f"\n[APPLICATION FORM] Custom cover letter generated successfully!")
                        
                        # Use the generated cover letter and make sure it gets filled
                        logger.info("Filling textarea with generated cover letter")
                        try:
                            # First clear any existing content
                            textarea_element.fill("")
                            time.sleep(0.5)  # Brief pause
                            
                            # Then fill with the generated cover letter
                            textarea_element.fill(custom_cover_letter)
                            logger.info(f"Successfully filled cover letter field with custom generated content")
                            
                            # Store that we used a generated cover letter and the content
                            answers['used_cover'] = True
                            answers[field_label] = custom_cover_letter  # Save for future reference
                            
                            # Save to disk immediately
                            answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
                            save_answers(answers_file, answers)
                            logger.info("Saved generated cover letter to answers file")
                            
                            return True
                        except Exception as fill_error:
                            logger.error(f"Error filling cover letter field: {fill_error}")
                            print(f"\n[APPLICATION FORM] Error filling cover letter field: {fill_error}")
                    except Exception as e:
                        logger.error(f"Error generating cover letter: {e}")
                        print(f"\n[APPLICATION FORM] Error generating cover letter: {e}. Using stored answer instead.")
                else:
                    logger.warning("Cannot generate cover letter: No job data available")
                    print(f"\n[APPLICATION FORM] Cannot generate cover letter: No job data available. Using stored answer instead.")
                    # Proceed with normal text filling
            
            # Standard field filling
            textarea_element.fill(answer)
            logger.info(f"Filled textarea '{field_label}' with answer")
            return True
        except PlaywrightError as e:
            logger.error(f"Error filling textarea '{field_label}': {e}")
            return False
