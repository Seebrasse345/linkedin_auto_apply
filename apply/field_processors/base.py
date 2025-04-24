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
        """Get input for a field, either automatically via answer_generator or from user.
        
        Args:
            field_label: The label of the field
            field_type: The type of field
            answers: Dictionary to store the answer
            options: Optional list of available options for select/radio fields
            
        Returns:
            str: The answer (automatic or user-provided)
        """
        try:
            # Import here to avoid circular imports
            from ..cover_letter_generator import answer_generator
            
            # Construct the question with options if available
            question = field_label
            if options:
                question += "\nOptions:\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
            
            print(f"\n[APPLICATION FORM] Automatically answering: {field_label} (Type: {field_type})")
            
            # Get job data if this is a text field
            job_data = None
            if field_type == "text" or field_type == "textarea":
                # Try to get job data from the processor or answers - matching pattern from text_processor.py
                effective_job_data = None
                
                # First check self.job_data (this is how text_processor.py accesses it)
                if hasattr(self, 'job_data') and self.job_data:
                    effective_job_data = self.job_data
                    logger.info("Using processor's job_data for text field answer generation")
                
                # Fallback to current_job_data in answers
                if not effective_job_data and 'current_job_data' in answers:
                    effective_job_data = answers['current_job_data']
                    logger.info("Using answers['current_job_data'] for text field answer generation")
                
                job_data = effective_job_data
                
                if job_data:
                    print(f"Including job description for text field: {field_label}")
                    logger.info(f"Job data for text field answer: ID={job_data.get('job_id', 'Unknown')}, Title={job_data.get('title', 'Unknown')}, Company={job_data.get('company', 'Unknown')}")
            
            # Get automatic answer
            auto_answer = answer_generator(question, field_type, job_data)
            
            if auto_answer:
                print(f"Auto-selected answer: {auto_answer}")
                
                # For numeric selections, convert back to the actual option text if options are provided
                if options and auto_answer.isdigit() and 0 < int(auto_answer) <= len(options):
                    option_index = int(auto_answer) - 1
                    actual_answer = options[option_index]
                    print(f"Selected option: {actual_answer}")
                    
                    # Save the actual text answer
                    answers[field_label] = actual_answer
                    return actual_answer
                
                # For text inputs, use the answer directly
                answers[field_label] = auto_answer
                return auto_answer
            
            # Fallback to manual input if automatic answer fails
            print(f"Could not get automatic answer, falling back to manual input")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error getting automatic answer: {e}")
            print(f"\n[APPLICATION FORM] Error getting automatic answer: {e}")
        
        # Manual input fallback
        print(f"\n[APPLICATION FORM] Need input for: {field_label} (Type: {field_type})")
        user_input = input("Please provide an answer: ")
        
        # Save the answer for future use
        answers[field_label] = user_input
        
        return user_input
