"""
Resume selection field processor for LinkedIn job application forms.
"""
import logging
from typing import Dict, Any
from playwright.sync_api import Locator, Error as PlaywrightError

from .base import FieldProcessor
from ..constants import RESUME_SELECTOR

logger = logging.getLogger(__name__)

class ResumeProcessor(FieldProcessor):
    """Processor for resume selection fields."""
    
    def process(self, page, answers: Dict[str, Any]) -> bool:
        """Skip resume selection - leave the default resume as is.
        
        Args:
            page: Playwright page
            answers: Dictionary of stored answers (not used)
            
        Returns:
            bool: True (always succeeds since we're skipping)
        """
        # First check if resume selector is present
        resume_elements = page.locator(RESUME_SELECTOR)
        
        if resume_elements.count() > 0:
            logger.info("Resume selector found but skipping selection as per user request")
        
        # Check for radio buttons related to resume selection - just log but don't interact
        resume_radios = page.locator('input[type="radio"][name*="resume"], div[role="radio"][aria-label*="resume"]')
        if resume_radios.count() > 0:
            logger.info(f"Found {resume_radios.count()} resume radio buttons but skipping selection")
        
        # Simply return true without changing anything
        return True
