"""
Checkbox field processor for LinkedIn job application forms.
"""
import logging
from typing import Dict, Any
from playwright.sync_api import Locator, Error as PlaywrightError

from .base import FieldProcessor
from ..helpers import get_answer_for_field

logger = logging.getLogger(__name__)

class CheckboxProcessor(FieldProcessor):
    """Processor for checkbox fields."""
    
    def process(self, checkbox_group: Locator, answers: Dict[str, Any]) -> bool:
        """Process a checkbox group.
        
        Args:
            checkbox_group: Playwright locator for the checkbox group
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # Similar approach as radio buttons, but multiple can be selected
        container = checkbox_group.first.locator("xpath=ancestor::div[contains(@class, 'form-component')][1]")
        field_label = ""
        
        if container.count() > 0:
            heading = container.locator("h3, h4, .fb-form-element-label")
            if heading.count() > 0:
                field_label = heading.first.inner_text().strip()
        
        if not field_label:
            field_label = self.get_field_label(checkbox_group.first)
        
        answer = get_answer_for_field(answers, field_label)
        
        try:
            # First try to find the label to click, which is often more reliable
            checkbox_id = checkbox_group.first.get_attribute("id")
            success = False
            
            # Try clicking the label first if available (often more reliable)
            if checkbox_id:
                label = checkbox_group.first.page.locator(f"label[for='{checkbox_id}']")
                if label.count() > 0:
                    try:
                        logger.info(f"Attempting to click label for checkbox '{field_label}'")
                        label.first.click(timeout=5000)
                        success = True
                        logger.info(f"Successfully clicked label for checkbox '{field_label}'")
                    except PlaywrightError as e:
                        logger.warning(f"Failed to click label for checkbox '{field_label}': {e}")
            
            # If label click failed, try direct checkbox manipulation
            if not success:
                # For simplicity, we'll just select the first checkbox if no specific answer
                if not answer or answer.lower() in ["yes", "true", "1"]:
                    try:
                        # Try multiple methods
                        if "type='checkbox'" in checkbox_group.first.evaluate("el => el.outerHTML"):
                            logger.info(f"Attempting to check checkbox '{field_label}' using check() method")
                            checkbox_group.first.check(timeout=5000)
                        else:
                            logger.info(f"Attempting to click checkbox '{field_label}' directly")
                            checkbox_group.first.click(timeout=5000)
                        
                        success = True
                        logger.info(f"Checked checkbox for '{field_label}'")
                    except PlaywrightError as e:
                        logger.warning(f"Failed direct checkbox interaction: {e}. Trying JavaScript click.")
                        try:
                            logger.info(f"Attempting JavaScript click on checkbox '{field_label}'")
                            checkbox_group.first.evaluate("el => el.click()")
                            success = True
                            logger.info(f"Successfully used JavaScript click on checkbox '{field_label}'")
                        except PlaywrightError as js_e:
                            logger.error(f"JavaScript click also failed: {js_e}")
                else:
                    # Uncheck if answer is explicitly "no"
                    if answer.lower() in ["no", "false", "0"] and checkbox_group.first.is_checked():
                        try:
                            if "type='checkbox'" in checkbox_group.first.evaluate("el => el.outerHTML"):
                                checkbox_group.first.uncheck(timeout=5000)
                            else:
                                checkbox_group.first.click(timeout=5000)
                            success = True
                            logger.info(f"Unchecked checkbox for '{field_label}'")
                        except PlaywrightError as e:
                            logger.warning(f"Failed to uncheck: {e}. Trying JavaScript click.")
                            try:
                                checkbox_group.first.evaluate("el => el.click()")
                                success = True
                                logger.info(f"Successfully used JavaScript click to uncheck '{field_label}'")
                            except PlaywrightError as js_e:
                                logger.error(f"JavaScript click also failed: {js_e}")
            
            return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing checkbox '{field_label}': {e}")
            return False
