"""
Select dropdown field processor for LinkedIn job application forms.
"""
import logging
from typing import Dict, Any, List
from playwright.sync_api import Locator, Error as PlaywrightError

from .base import FieldProcessor
from ..helpers import get_answer_for_field

logger = logging.getLogger(__name__)

class SelectProcessor(FieldProcessor):
    """Processor for select dropdown fields."""
    
    def process(self, select_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a select dropdown field.
        
        Args:
            select_element: Playwright locator for the select element
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        field_label = self.get_field_label(select_element)
        answer = get_answer_for_field(answers, field_label)
        
        try:
            # Get available options
            options = []
            for option in select_element.locator("option").all():
                option_text = option.inner_text().strip()
                if option_text and option_text != "Select an option":
                    options.append(option_text)
            
            if not options:
                logger.warning(f"No options found for select '{field_label}'")
                return False
            
            # Always ask for dropdown fields that are important qualifications
            if not answer or 'experience' in field_label.lower() or 'qualification' in field_label.lower() or 'degree' in field_label.lower() or 'education' in field_label.lower() or 'skill' in field_label.lower():
                # Show options to user
                print(f"\n[APPLICATION FORM] Select an option for: {field_label}")
                for i, option in enumerate(options):
                    print(f"{i+1}. {option}")
                
                # Robust input handling with retry
                while True:
                    try:
                        selection = input(f"Enter option number (1-{len(options)}): ")
                        index = int(selection) - 1
                        if 0 <= index < len(options):
                            answer = options[index]
                            break
                        else:
                            print(f"Invalid selection. Please enter a number between 1 and {len(options)}.")
                    except (ValueError, KeyboardInterrupt):
                        print("Please enter a valid number.")
                
                # Save the answer
                answers[field_label] = answer
                
                # Immediately save to disk
                try:
                    from ..helpers import save_answers
                    import os
                    
                    # Get answers file path from the ApplicationWizard context
                    answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
                    save_answers(answers_file, answers)
                    logger.info(f"Saved new answer for '{field_label}' immediately to disk")
                except Exception as e:
                    logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
            
            # Try to select by value or label
            if answer in options:
                select_element.select_option(label=answer)
                logger.info(f"Selected option '{answer}' for '{field_label}'")
                return True
            else:
                # If we don't have an exact match, ask the user to select instead of guessing
                print(f"\n[APPLICATION FORM] No exact match found for '{answer}'. Please select an option for: {field_label}")
                for i, option in enumerate(options):
                    print(f"{i+1}. {option}")
                
                # Robust input handling with retry
                selected_option = ""
                while True:
                    try:
                        selection = input(f"Enter option number (1-{len(options)}): ")
                        index = int(selection) - 1
                        if 0 <= index < len(options):
                            selected_option = options[index]
                            # Update the saved answer for future use
                            answers[field_label] = selected_option
                            break
                        else:
                            print(f"Invalid selection. Please enter a number between 1 and {len(options)}.")
                    except (ValueError, KeyboardInterrupt):
                        print("Please enter a valid number.")
                
                select_element.select_option(label=selected_option)
                logger.info(f"Selected user-chosen option '{selected_option}' for '{field_label}'")
                return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing select '{field_label}': {e}")
            return False
