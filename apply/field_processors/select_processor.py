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
        
        try:
            # Get available options
            options = []
            option_values = []
            for option in select_element.locator("option").all():
                text = option.inner_text().strip()
                value = option.get_attribute("value")
                if text and "select" not in text.lower():
                    options.append(text)
                    option_values.append(value)

            if not options:
                logger.warning(f"No options found for select '{field_label}'")
                return False

            # For unlabeled fields, enhance the field_label with option information
            # to differentiate between different unlabeled dropdowns
            if field_label == "Unlabeled field" and options:
                enhanced_label = f"{field_label} ({'/'.join(options[:2])})" 
                logger.info(f"Enhanced unlabeled field label to: '{enhanced_label}'")
                field_label = enhanced_label

            # Determine final answer: stored or generated
            answer = answers.get(field_label)
            if not answer:
                for k, v in answers.items():
                    if k.lower() == field_label.lower():
                        answer = v
                        break
                    # Try to match enhanced labels to previous base labels
                    elif field_label.startswith("Unlabeled field") and k == "Unlabeled field":
                        # Check if stored answer is in our options list
                        if v in options:
                            answer = v
                            logger.info(f"Matched unlabeled field base answer: '{v}'")
                            break
                        
            if not answer:
                logger.info(f"No stored answer for '{field_label}', generating via GPT")
                # Pass all options to GPT for better context
                question_with_options = f"{field_label}\nOptions:\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
                answer = self.ask_for_input(question_with_options, "select", answers, options)
                
                # If answer is numeric and within range, convert to option text
                if answer and answer.isdigit() and 0 < int(answer) <= len(options):
                    index = int(answer) - 1
                    answer = options[index]
                    logger.info(f"Converted numeric answer to option text: '{answer}'")
                
                answers[field_label] = answer
                try:
                    from ..helpers import save_answers
                    import os
                    ans_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
                    save_answers(ans_file, answers)
                except Exception as e:
                    logger.warning(f"Could not save answer for '{field_label}': {e}")

            # Match answer to options
            selected = None
            # Exact match
            for opt in options:
                if opt.lower() == answer.lower():
                    selected = opt
                    break
            # Partial match
            if not selected and answer:
                for opt in options:
                    if (answer.lower() in opt.lower() or opt.lower() in answer.lower()) and len(answer) > 2:
                        selected = opt
                        break
            
            # If still no match, generate a new answer specifically for this dropdown
            # This ensures each dropdown gets its own tailored response
            if not selected:
                logger.warning(f"No match for answer '{answer}' in options {options}, getting specific answer")
                # Create a more specific prompt with field position info to differentiate unlabeled fields
                specific_prompt = f"Select field {field_label} with options: {', '.join(options)}"
                specific_answer = self.ask_for_input(specific_prompt, "select", answers, options)
                
                # Try to match the new specific answer
                for opt in options:
                    if opt.lower() == specific_answer.lower() or (len(specific_answer) > 2 and 
                       (specific_answer.lower() in opt.lower() or opt.lower() in specific_answer.lower())):
                        selected = opt
                        logger.info(f"Found match for specific answer '{specific_answer}': '{selected}'")
                        break
                        
                # Update the stored answer with this better match
                if selected:
                    answers[field_label] = selected
                    try:
                        from ..helpers import save_answers
                        import os
                        ans_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                              'answers', 'default.json')
                        save_answers(ans_file, answers)
                    except Exception as e:
                        logger.warning(f"Could not save specific answer: {e}")
            
            # Fallback to first option only as last resort
            if not selected:
                selected = options[0]
                logger.warning(f"Fallback select '{selected}' for '{field_label}'")

            select_element.select_option(label=selected)
            logger.info(f"Selected '{selected}' for '{field_label}'")
            answers[field_label] = selected
            return True
        except PlaywrightError as e:
            logger.error(f"Error processing select '{field_label}': {e}")
            return False
