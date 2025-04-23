"""
Constants for LinkedIn application automation.
Contains all selectors and application status constants.
"""
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Application status constants
APPLICATION_SUCCESS = "success"
APPLICATION_FAILURE = "failure"
APPLICATION_INCOMPLETE = "incomplete"

# Selectors
EASY_APPLY_BUTTON_SELECTOR = "button.jobs-apply-button"

# Navigation button selectors (will be used within the application modal context)
NEXT_BUTTON_SELECTOR = "button[aria-label='Continue to next step'], button[aria-label='Review your application'], footer div:has-text('Next'), button:has-text('Next'), button[data-easy-apply-next-button]"
SUBMIT_BUTTON_SELECTOR = "button[aria-label='Submit application'], button:has-text('Submit application')"
DONE_BUTTON_SELECTOR = "button[aria-label='Done'], button[aria-label='Dismiss'], button:has-text('Done'), button:has-text('Dismiss')"

# Application modal selector - narrowed to specifically target the application modal
APPLICATION_MODAL_SELECTOR = "div.artdeco-modal__content.jobs-easy-apply-modal__content, div.jobs-easy-apply-content"

# Form field selectors (scoped to the application modal)
TEXT_INPUT_SELECTOR = "input[type='text']"
TEXTAREA_SELECTOR = "textarea"
SELECT_SELECTOR = "select"
RADIO_SELECTOR = "input[type='radio'], div[role='radio']"
CHECKBOX_SELECTOR = "input[type='checkbox'], div[role='checkbox']"
RESUME_SELECTOR = "[data-test-resume-selector-resume-card]"
