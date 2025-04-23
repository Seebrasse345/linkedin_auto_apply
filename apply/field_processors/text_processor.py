"""
Text input and textarea field processors for LinkedIn job application forms.
"""
import logging
import os
from os import path
from typing import Dict, Any
from playwright.sync_api import Locator, Error as PlaywrightError

from .base import FieldProcessor
from ..helpers import get_answer_for_field, save_answers

logger = logging.getLogger(__name__)

class TextInputProcessor(FieldProcessor):
    """Processor for text input fields."""
    
    def process(self, input_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a text input field.
        
        Args:
            input_element: Playwright locator for the input element
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        field_label = self.get_field_label(input_element)
        answer = get_answer_for_field(answers, field_label)
        
        if not answer:
            answer = self.ask_for_input(field_label, "text", answers)
        
        # Save answer for future use
        answers[field_label] = answer
        
        # Immediately save to disk
        try:
            answers_file = path.join(path.dirname(path.dirname(path.dirname(__file__))), 'answers', 'default.json')
            save_answers(answers_file, answers)
            logger.info(f"Saved new answer for '{field_label}' immediately to disk")
        except Exception as e:
            logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
        
        try:
            input_element.fill(answer)
            logger.info(f"Filled text input '{field_label}' with answer")
            return True
        except PlaywrightError as e:
            logger.error(f"Error filling text input '{field_label}': {e}")
            return False


class TextareaProcessor(FieldProcessor):
    """Processor for textarea fields."""
    
    def process(self, textarea_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a textarea field.
        
        Args:
            textarea_element: Playwright locator for the textarea element
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        field_label = self.get_field_label(textarea_element)
        answer = get_answer_for_field(answers, field_label)
        
        if not answer:
            answer = self.ask_for_input(field_label, "textarea", answers)
        
        try:
            textarea_element.fill(answer)
            logger.info(f"Filled textarea '{field_label}' with answer")
            return True
        except PlaywrightError as e:
            logger.error(f"Error filling textarea '{field_label}': {e}")
            return False
