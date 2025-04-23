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
    
    def ask_for_input(self, field_label: str, field_type: str, answers: Dict[str, Any]) -> str:
        """Ask the user for input when an answer is not available.
        
        Args:
            field_label: The label of the field
            field_type: The type of field
            answers: Dictionary to store the answer
            
        Returns:
            str: The user's input
        """
        print(f"\n[APPLICATION FORM] Need input for: {field_label} (Type: {field_type})")
        user_input = input("Please provide an answer: ")
        
        # Save the answer for future use
        answers[field_label] = user_input
        
        return user_input
