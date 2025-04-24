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
        
        # Define critical question keywords that ALWAYS require user input
        critical_keywords = ['legal', 'authorization', 'authorisation', 'visa', 'sponsor', 'citizen', 'work', 'right']
        
        # Check if this is a critical question that requires explicit user input
        is_critical_question = any(keyword in field_label.lower() for keyword in critical_keywords)
        
        # Get stored answer using strict matching only
        answer = None
        if field_label in answers:
            answer = answers[field_label]
            logger.info(f"Found exact stored answer for '{field_label}'")
        else:
            # Try case-insensitive match as fallback
            for key, value in answers.items():
                if key.lower() == field_label.lower():
                    answer = value
                    logger.info(f"Found case-insensitive stored answer for '{field_label}'")
                    break
        
        # For critical questions, ALWAYS prompt the user regardless of stored answers
        if is_critical_question:
            logger.info(f"CRITICAL QUESTION DETECTED: '{field_label}' - will always prompt user")
            answer = None  # Force user input for critical questions
        
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
            
            # Prompt user if: 
            # 1. No stored answer exists, OR
            # 2. Stored answer doesn't match available options, OR
            # 3. This is a critical question (work authorization, etc.)
            if not answer or answer not in options or is_critical_question:
                # Use automatic answer generator instead of prompting user
                answer = self.ask_for_input(field_label, "select", answers, options)
                
                # Save the answer
                answers[field_label] = answer
                
                # Immediately save to disk
                try:
                    from ..helpers import save_answers
                    import os
                    
                    # Get answers file path directly
                    answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
                    save_answers(answers_file, answers)
                    logger.info(f"Saved new answer for '{field_label}' immediately to disk")
                except Exception as e:
                    logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
            
            # If we have a stored answer that exactly matches an option, select it
            # Note: At this point we've already filtered out critical questions
            if answer and answer in options:
                select_element.select_option(label=answer)
                logger.info(f"Selected verified stored option '{answer}' for '{field_label}'")
                return True
            # If we have a stored answer but it doesn't match exactly, ask the user
            elif answer:
                # Show stored answer but ask for confirmation
                print(f"\n[APPLICATION FORM] Your stored answer '{answer}' doesn't match available options for: {field_label}")
                print("Available options:")
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
            # No stored answer case - try auto-answer first, then prompt user for input
            else:
                # Check if this is a common question that we can auto-answer
                field_lower = field_label.lower()
                # Remote-related questions
                if any(kw in field_lower for kw in ['remote', 'work from home', 'wfh', 'telecommut', 'home working']):
                    # Find the 'Yes' option
                    auto_answer = None
                    for option in options:
                        if option.lower() == 'yes':
                            auto_answer = option
                            logger.info(f"Auto-answering remote work question for '{field_label}' with '{auto_answer}'")
                            break
                # Commute/location questions
                elif any(kw in field_lower for kw in ['commut', 'locat', 'relocat', 'travel', 'on-site']):
                    # Find the 'Yes' option
                    auto_answer = None
                    for option in options:
                        if option.lower() == 'yes':
                            auto_answer = option
                            logger.info(f"Auto-answering commute/location question for '{field_label}' with '{auto_answer}'")
                            break
                # Visa/sponsorship questions
                elif any(kw in field_lower for kw in ['visa', 'sponsor']):
                    # Find the 'No' option
                    auto_answer = None
                    for option in options:
                        if option.lower() == 'no':
                            auto_answer = option
                            logger.info(f"Auto-answering visa/sponsorship question for '{field_label}' with '{auto_answer}'")
                            break
                # Years of experience questions
                elif any(kw in field_lower for kw in ['years of experience', 'years of work experience', 'how many years']):
                    # Try to find options with '0-2', '1-3', '2-5' or similar patterns, or '2 years' etc.
                    auto_answer = None
                    for option in options:
                        if ('0-2' in option or '1-3' in option or '0-1' in option or 
                            '2 years' in option.lower() or '1-2' in option or 
                            option == '2'):
                            auto_answer = option
                            logger.info(f"Auto-answering years of experience question for '{field_label}' with '{auto_answer}'")
                            break
                # For other questions, use the answer_generator
                else:
                    auto_answer = None
                
                # If we have auto-answer, use it, otherwise call ask_for_input
                if auto_answer:
                    selected_option = auto_answer
                    # Save the answer for future use
                    answers[field_label] = selected_option
                else:
                    # Use automatic answer generator
                    selected_option = self.ask_for_input(field_label, "select", answers, options)
                
                # Immediately save to disk
                try:
                    from ..helpers import save_answers
                    import os
                    
                    # Get answers file path directly
                    answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
                    save_answers(answers_file, answers)
                    logger.info(f"Saved new answer for '{field_label}' immediately to disk")
                except Exception as e:
                    logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
                
                select_element.select_option(label=selected_option)
                logger.info(f"Selected user-chosen option '{selected_option}' for '{field_label}'")
                return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing select '{field_label}': {e}")
            return False
