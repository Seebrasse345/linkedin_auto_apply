"""
Base field processor class for LinkedIn job application forms.
"""
import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from playwright.sync_api import Locator, Error as PlaywrightError

logger = logging.getLogger(__name__)

class FieldProcessor(ABC):
    """Base class for field processors."""
    
    def __init__(self):
        """Initialize the field processor."""
        self.job_data = {}
    
    @abstractmethod
    def process(self, field_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a form field element.
        
        Args:
            field_element: Playwright locator for the field element
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        pass
    
    def get_field_label(self, field_element: Locator) -> str:
        """Extract the label text for a form field.
        
        Args:
            field_element: Playwright locator for the field element
            
        Returns:
            str: The extracted label text
        """
        # Try to get label via for attribute
        field_id = field_element.get_attribute("id")
        if field_id:
            page = field_element.page
            label = page.locator(f"label[for='{field_id}']")
            if label.count() > 0:
                return label.first.inner_text().strip()
        
        # Try to get label from parent or ancestor elements
        try:
            # Try to find label in parent
            parent = field_element.locator("xpath=..")
            if parent.count() > 0:
                label = parent.locator("label, .fb-form-element__label, .fb-dash-form-element__label")
                if label.count() > 0:
                    return label.first.inner_text().strip()
                
            # For radio buttons or fields inside a fieldset, try to get the legend text
            # This is critical for questions like "Are you comfortable commuting?"
            if field_element.get_attribute("type") == "radio" or field_element.get_attribute("role") == "radio":
                # First try to get the fieldset legend
                fieldset = field_element.locator("xpath=ancestor::fieldset[1]")
                if fieldset.count() > 0:
                    legend = fieldset.locator("legend")
                    if legend.count() > 0:
                        # Extract text from span inside legend
                        span = legend.locator("span span")
                        if span.count() > 0:
                            return span.first.inner_text().strip()
                        return legend.inner_text().strip()
                    
            # Try to find in ancestor div with form-component class
            ancestor = field_element.locator("xpath=ancestor::div[contains(@class, 'form-component')][1]")
            if ancestor.count() > 0:
                label = ancestor.locator("label, .fb-form-element__label, legend, h3, h4, .fb-dash-form-element__label")
                if label.count() > 0:
                    return label.first.inner_text().strip()
                
                # Try to find a deeper span that might contain the label
                label_span = ancestor.locator("span span")
                if label_span.count() > 0:
                    return label_span.first.inner_text().strip()
                
            # If the field is a radio, try to get the value
            if field_element.get_attribute("type") == "radio":
                return field_element.get_attribute("value") or ""
                
            # Try the immediate containing div's attribute for field name
            form_div = field_element.locator("xpath=ancestor::div[contains(@class, 'fb-dash-form-element')][1]")
            if form_div.count() > 0:
                field_id = form_div.get_attribute("id")
                if field_id and "formElement" in field_id:
                    # Extract field name from the ID
                    field_name = field_id.split("-")[-1] if "-" in field_id else ""
                    if field_name:
                        return field_name.replace("-", " ").title()
        except Exception as e:
            logger.error(f"Error getting field label: {e}")
        
        # If all else fails, return a placeholder with the field type
        field_type = field_element.get_attribute("type") or "field"
        return f"Unlabeled {field_type}"
    
    def ask_for_input(self, field_label: str, field_type: str, answers: Dict[str, Any], options: list = None) -> str:
        """Get input for a field ALWAYS via answer_generator and NEVER from user.
        
        Args:
            field_label: The label of the field
            field_type: The type of field
            answers: Dictionary to store the answer
            options: Optional list of available options for select/radio fields
            
        Returns:
            str: The answer (always automatically generated)
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Auto-generating answer for '{field_label}' (Type: {field_type})")
        
        # Import here to avoid circular imports
        from ..cover_letter_generator import answer_generator
        
        # Construct the question with options if available
        question = field_label
        if options:
            question += "\nOptions:\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        
        # Get job data for context
        job_data = None
        # First check self.job_data (this is how text_processor.py accesses it)
        if hasattr(self, 'job_data') and self.job_data:
            job_data = self.job_data
            logger.info(f"Using processor's job_data for answer generation")
        # Fallback to current_job_data in answers
        elif 'current_job_data' in answers:
            job_data = answers['current_job_data']
            logger.info(f"Using answers['current_job_data'] for answer generation")
        
        if job_data:
            logger.info(f"Job context: ID={job_data.get('job_id', 'Unknown')}, Title={job_data.get('title', 'Unknown')}, Company={job_data.get('company', 'Unknown')}")
        
        try:
            # Always attempt to generate an answer
            auto_answer = answer_generator(question, field_type, job_data)
            
            # Check for the special fallback format (tuple indicates fallback answer that shouldn't be saved)
            is_fallback = False
            if isinstance(auto_answer, tuple) and len(auto_answer) == 2 and auto_answer[0] is False:
                is_fallback = True
                if auto_answer[1]:
                    auto_answer = auto_answer[1]  # Use provided fallback if available
                else:
                    auto_answer = ""  # Otherwise empty string
                logger.warning(f"Using temporary fallback answer for '{field_label}' (will not be saved)")
            else:
                logger.info(f"Generated answer for '{field_label}': {auto_answer if len(str(auto_answer)) < 50 else auto_answer[:50]+'...'}")
            
            # For numeric selections, convert to the actual option text
            if options and auto_answer and auto_answer.isdigit() and 0 < int(auto_answer) <= len(options):
                option_index = int(auto_answer) - 1
                actual_answer = options[option_index]
                logger.info(f"Converted numeric answer to option text: '{actual_answer}'")
                if not is_fallback:  # Only save if not a fallback
                    answers[field_label] = actual_answer
                return actual_answer
            
            # Special handling for yes/no questions with options
            if options and len(options) == 2 and auto_answer:
                yes_no_map = {'yes': 0, 'no': 1}
                auto_lower = auto_answer.lower()
                if auto_lower in yes_no_map and ('yes' in options[0].lower() or 'no' in options[1].lower()):
                    selected = options[yes_no_map[auto_lower]]
                    logger.info(f"Mapped yes/no answer to option: '{selected}'")
                    if not is_fallback:  # Only save if not a fallback
                        answers[field_label] = selected
                    return selected
            
            # For all other cases, use the answer directly
            if auto_answer:
                if not is_fallback:  # Only save if not a fallback
                    answers[field_label] = auto_answer
                return auto_answer
            
            # If no answer was generated, use a safe default but don't save it
            logger.warning(f"No answer generated for '{field_label}', using temporary default (will not be saved)")
            is_fallback = True  # Mark as fallback since we're using defaults
            if field_type in ['radio', 'select'] and options:
                # For yes/no questions, prefer 'yes' for remote/commute, 'no' for visa/sponsor
                field_lower = field_label.lower()
                if len(options) == 2:
                    if any(kw in field_lower for kw in ['visa', 'sponsor', 'right to work', 'non-compete', 'competitor']):
                        for i, opt in enumerate(options):
                            if 'no' in opt.lower():
                                logger.info(f"Using default 'No' for '{field_label}'")
                                if not is_fallback:
                                    answers[field_label] = opt
                                return opt
                    elif any(kw in field_lower for kw in ['remote', 'commut', 'relocat', 'travel']):
                        for i, opt in enumerate(options):
                            if 'yes' in opt.lower():
                                logger.info(f"Using default 'Yes' for '{field_label}'")
                                if not is_fallback:
                                    answers[field_label] = opt
                                return opt
                
                # No special case, use first option
                default = options[0]
                logger.info(f"Using first option as default: '{default}'")
                if not is_fallback:
                    answers[field_label] = default
                return default
            elif field_type in ['text', 'textarea']:
                # For text fields, return a generic response
                if 'experience' in field_label.lower():
                    default = "2"
                else:
                    default = "Yes, I am interested in this position and meet the requirements."
                logger.info(f"Using generic text as default: '{default}'")
                if not is_fallback:
                    answers[field_label] = default
                return default
            
            # Ultimate fallback
            default = "Yes" if field_type in ['radio', 'select'] else "2"
            logger.info(f"Using ultimate fallback: '{default}'")
            answers[field_label] = default
            return default
            
        except Exception as e:
            logger.error(f"Error generating answer for '{field_label}': {e}")
            # Emergency fallback - never ask for user input
            if field_type in ['radio', 'select'] and options:
                default = options[0]  # Use first option as safest fallback
                logger.info(f"Emergency fallback to first option: '{default}'")
                answers[field_label] = default
                return default
            else:
                default = "2" if 'experience' in field_label.lower() else "Yes"
                logger.info(f"Emergency fallback to default text: '{default}'")
                answers[field_label] = default
                return default
