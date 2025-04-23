"""
Form processor for LinkedIn job application forms.
Handles the overall form processing logic and field type delegation.
"""
import logging
from typing import Dict, Any, List
from playwright.sync_api import Page, Locator, Error as PlaywrightError

from .constants import APPLICATION_MODAL_SELECTOR
from .field_processors import (
    TextInputProcessor, 
    TextareaProcessor, 
    SelectProcessor, 
    RadioProcessor,
    RadioGroupProcessor,
    CheckboxProcessor,
    ResumeProcessor
)

logger = logging.getLogger(__name__)

class FormProcessor:
    """Processes LinkedIn job application forms by handling different field types."""
    
    def __init__(self, page: Page, answers: Dict[str, Any]):
        """Initialize the form processor.
        
        Args:
            page: Playwright page
            answers: Dictionary of stored answers
        """
        self.page = page
        self.answers = answers
        
        # Initialize field processors
        self.text_processor = TextInputProcessor()
        self.textarea_processor = TextareaProcessor()
        self.select_processor = SelectProcessor()
        self.radio_processor = RadioProcessor()
        self.radio_group_processor = RadioGroupProcessor(page)
        self.checkbox_processor = CheckboxProcessor()
        self.resume_processor = ResumeProcessor()
    
    def process_form_fields(self) -> bool:
        """Process all form fields on the current step.
        
        Returns:
            bool: True if processing succeeded for all fields, False otherwise
        """
        success = True
        try:
            modal = self.page.locator(APPLICATION_MODAL_SELECTOR)
            if modal.count() == 0:
                logger.error("Application form modal not found")
                return False
            
            app_modal = modal.first
            logger.info("Application form modal found, processing fields")
            
            # Process all input types in the modal
            text_inputs = app_modal.locator("input[type='text']:visible, input:not([type]):visible")
            logger.info(f"Found {text_inputs.count()} text input fields in form")
            
            for i in range(text_inputs.count()):
                if not self.text_processor.process(text_inputs.nth(i), self.answers):
                    success = False
            
            textareas = app_modal.locator("textarea:visible")
            logger.info(f"Found {textareas.count()} textarea fields in form")
            
            for i in range(textareas.count()):
                if not self.textarea_processor.process(textareas.nth(i), self.answers):
                    success = False
            
            selects = app_modal.locator("select:visible")
            logger.info(f"Found {selects.count()} select fields in form")
            
            for i in range(selects.count()):
                if not self.select_processor.process(selects.nth(i), self.answers):
                    success = False
            
            # Find all fieldsets that contain radio buttons - these are separate question groups
            radio_fieldsets = app_modal.locator("fieldset:has(input[type='radio']), fieldset:has(div[role='radio'])")
            if radio_fieldsets.count() > 0:
                logger.info(f"Found {radio_fieldsets.count()} radio button groups/fieldsets in form")
                
                # Process each fieldset as a separate radio button group
                for i in range(radio_fieldsets.count()):
                    fieldset = radio_fieldsets.nth(i)
                    if not self.radio_group_processor.process_radio_group(fieldset, self.answers):
                        success = False
            else:
                # Fallback for radio buttons not in fieldsets
                radio_buttons = app_modal.locator("input[type='radio'], div[role='radio']")
                logger.info(f"Found {radio_buttons.count()} individual radio buttons in form")
                
                if radio_buttons.count() > 0:
                    # Try to group by name attribute or parent container
                    grouped_radios = self.radio_group_processor.group_radio_buttons(radio_buttons)
                    for group_name, group_elements in grouped_radios.items():
                        logger.info(f"Processing radio group '{group_name}' with {len(group_elements)} options")
                        if not self.radio_group_processor.process_radio_from_group(group_name, group_elements, self.answers):
                            success = False
            
            checkbox_groups = app_modal.locator("input[type='checkbox']:visible, div[role='checkbox']:visible")
            logger.info(f"Found {checkbox_groups.count()} checkbox fields in form")
            
            if checkbox_groups.count() > 0:
                if not self.checkbox_processor.process(checkbox_groups, self.answers):
                    success = False
            
            # Process resume selector if present
            if not self.resume_processor.process(self.page, self.answers):
                success = False
            
            return success
            
        except PlaywrightError as e:
            logger.error(f"Error processing form fields: {e}")
            return False
