"""
Radio button field processors for LinkedIn job application forms.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from playwright.sync_api import Locator, Page, Error as PlaywrightError

from .base import FieldProcessor
from ..helpers import get_answer_for_field, should_auto_answer, get_auto_answer

logger = logging.getLogger(__name__)

class RadioProcessor(FieldProcessor):
    """Processor for radio button fields."""
    
    def process(self, radio_group: Locator, answers: Dict[str, Any]) -> bool:
        """Process a radio button group.
        
        Args:
            radio_group: Playwright locator for the radio buttons group
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # First, try to determine the field label from fieldset/legend
        field_label = ""
        fieldset = radio_group.first.locator("xpath=ancestor::fieldset[1]")
        
        if fieldset.count() > 0:
            legend = fieldset.locator("legend")
            if legend.count() > 0:
                # Get the text from any span inside the legend
                span = legend.locator("span")
                if span.count() > 0:
                    for i in range(span.count()):
                        span_text = span.nth(i).inner_text().strip()
                        if span_text:
                            field_label = span_text
                            break
                else:
                    field_label = legend.inner_text().strip()
        
        # If we still don't have a label, try other methods
        if not field_label:
            container = radio_group.first.locator("xpath=ancestor::div[contains(@class, 'form-component')][1]")
            if container.count() > 0:
                heading = container.locator("h3, h4, .fb-form-element-label")
                if heading.count() > 0:
                    field_label = heading.first.inner_text().strip()
        
        # Last resort: try to get the label directly from the radio button
        if not field_label:
            field_label = self.get_field_label(radio_group.first)
        
        logger.info(f"Processing radio group: '{field_label}'")
        answer = get_answer_for_field(answers, field_label)
        
        try:
            # Get available options
            options, option_elements, option_labels = self._get_radio_options(radio_group)
            
            # Log what we found
            logger.info(f"Found {len(options)} radio options for '{field_label}': {options}")
            
            if not options or not option_elements:
                logger.warning(f"Could not determine options for radio group '{field_label}'")
                # Just click the first radio button as default
                try:
                    if radio_group.count() > 0:
                        # First try to get the label for the first radio button and click that
                        first_id = radio_group.first.get_attribute("id")
                        if first_id:
                            page = radio_group.first.page
                            first_label = page.locator(f"label[for='{first_id}']")
                            if first_label.count() > 0:
                                first_label.first.click()
                                logger.info(f"Clicked first radio button's label for '{field_label}'")
                                return True
                        
                        # If no label, try clicking the radio directly
                        radio_group.first.click()
                        logger.info(f"Clicked first radio button for '{field_label}'")
                        return True
                except PlaywrightError as e:
                    logger.warning(f"Failed to click first radio: {e}. Will try JS click.")
                    try:
                        radio_group.first.evaluate("el => el.click()")
                        logger.info("Used JS click on first radio button")
                        return True
                    except PlaywrightError as js_e:
                        logger.error(f"JS click also failed: {js_e}")
                return False
            
            # Skip resume selection per user request
            if field_label.lower().find('resume') >= 0 or field_label.lower().find('cv') >= 0:
                logger.info(f"Skipping resume/CV radio field: '{field_label}'")
                return True
            
            # Special handling for yes/no questions 
            if len(options) == 2 and any(opt.lower() in ['yes', 'no'] for opt in options):
                yes_index = next((i for i, opt in enumerate(options) if opt.lower() == 'yes'), -1)
                no_index = next((i for i, opt in enumerate(options) if opt.lower() == 'no'), -1)
                
                if yes_index >= 0 and no_index >= 0:
                    answer_index = -1
                    
                    # For disability questions, prefer "No"
                    if 'disability' in field_label.lower() or 'disabled' in field_label.lower():
                        answer_index = no_index
                        answer_text = "No"
                    # For location/commute questions, prefer "Yes" 
                    elif any(kw in field_label.lower() for kw in ['commut', 'locat', 'relocat', 'move', 'travel']):
                        answer_index = yes_index
                        answer_text = "Yes"
                    # For experience or qualification questions, prefer "Yes"
                    elif any(kw in field_label.lower() for kw in ['experience', 'work', 'skill', 'qualified', 'eligible']):
                        answer_index = yes_index
                        answer_text = "Yes"
                    
                    if answer_index >= 0:
                        if self._click_radio_option(option_elements[answer_index], option_labels[answer_index]):
                            logger.info(f"Selected '{answer_text}' for question: '{field_label}'")
                            return True
                        return False
            
            # For required questions without stored answers, make an automatic selection rather than prompting
            if not answer:
                selected_index = -1
                
                # Make an intelligent default choice based on the field type
                if 'commut' in field_label.lower() or 'location' in field_label.lower():
                    # For commuting questions, prefer "Yes"
                    yes_index = next((i for i, opt in enumerate(options) if opt.lower() == 'yes'), -1)
                    if yes_index >= 0:
                        selected_index = yes_index
                elif 'gender' in field_label.lower() or 'sex' in field_label.lower():
                    # Default to "Prefer not to say" for gender if available
                    prefer_not_say_index = next((i for i, opt in enumerate(options) if 'prefer not' in opt.lower()), -1)
                    if prefer_not_say_index >= 0:
                        selected_index = prefer_not_say_index
                    else:
                        selected_index = 0  # Default to first option
                elif 'ethnicity' in field_label.lower() or 'race' in field_label.lower():
                    # Default to "Prefer not to say" or "White" for ethnicity
                    prefer_not_say_index = next((i for i, opt in enumerate(options) if 'prefer not' in opt.lower()), -1)
                    white_index = next((i for i, opt in enumerate(options) if 'white' in opt.lower()), -1)
                    if prefer_not_say_index >= 0:
                        selected_index = prefer_not_say_index
                    elif white_index >= 0:
                        selected_index = white_index
                    else:
                        selected_index = 0
                elif 'veteran' in field_label.lower() or 'military' in field_label.lower():
                    # Default to "No" for veteran status
                    no_index = next((i for i, opt in enumerate(options) if opt.lower() == 'no'), -1)
                    if no_index >= 0:
                        selected_index = no_index
                    else:
                        selected_index = 0
                else:
                    # Default to first option for other fields
                    selected_index = 0
                
                if selected_index >= 0:
                    if self._click_radio_option(option_elements[selected_index], option_labels[selected_index]):
                        logger.info(f"Auto-selected option '{options[selected_index]}' for '{field_label}'")
                        
                        # Save this answer for future use
                        answers[field_label] = options[selected_index]
                        return True
                    return False
            
            # Try to find exact or similar match for stored answer
            selected = False
            for i, option_text in enumerate(options):
                if (answer and (answer.lower() == option_text.lower() or 
                    answer.lower() in option_text.lower() or 
                    option_text.lower() in answer.lower())):
                    if self._click_radio_option(option_elements[i], option_labels[i]):
                        logger.info(f"Selected radio option '{option_text}' for '{field_label}'")
                        selected = True
                        break
            
            # If no match, select first option
            if not selected and option_elements and len(option_elements) > 0:
                if self._click_radio_option(option_elements[0], option_labels[0]):
                    logger.info(f"Selected first radio option '{options[0]}' for '{field_label}'")
                    return True
                return False
            
            return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing radio group '{field_label}': {e}")
            return False
            
    def _click_radio_option(self, radio_element: Locator, label_element: Optional[Locator]) -> bool:
        """Helper to click a radio button with multiple fallback strategies.
        
        Args:
            radio_element: Playwright locator for the radio button
            label_element: Playwright locator for the label (can be None)
            
        Returns:
            bool: True if click succeeded, False otherwise
        """
        try:
            # First try label click if available (more reliable)
            if label_element is not None and label_element.count() > 0:
                label_element.click()
                return True
            else:
                # Try direct click on radio button
                radio_element.click()
                return True
        except PlaywrightError as e:
            logger.warning(f"Error with regular click: {e}. Trying JavaScript click.")
            try:
                # Try JS click as fallback
                radio_element.evaluate("el => el.click()")
                return True
            except PlaywrightError as js_e:
                logger.error(f"JS click also failed: {js_e}")
                return False
                
    def _get_radio_options(self, radio_group: Locator) -> Tuple[List[str], List[Locator], List[Optional[Locator]]]:
        """Get the options and elements for a radio button group.
        
        Args:
            radio_group: Playwright locator for the radio group
            
        Returns:
            Tuple containing:
            - List of option labels (strings)
            - List of radio button elements
            - List of label elements (can contain None values)
        """
        options = []
        option_elements = []
        option_labels = []
        page = radio_group.first.page
        
        # Try to find labels associated with the radio buttons
        for i in range(radio_group.count()):
            radio = radio_group.nth(i)
            radio_html = radio.evaluate("el => el.outerHTML")
            radio_id = radio.get_attribute("id")
            
            if "role='radio'" in radio_html or radio.get_attribute("role") == "radio":
                # Modern LinkedIn UI uses div with role="radio"
                label_text = radio.inner_text().strip()
                if not label_text and radio_id:
                    label = page.locator(f"label[for='{radio_id}']")
                    if label.count() > 0:
                        label_text = label.first.inner_text().strip()
                options.append(label_text or f"Option {i+1}")
                option_elements.append(radio)
                option_labels.append(None)  # No separate label element
            elif radio.get_attribute("type") == "radio":
                # Traditional radio buttons
                if radio_id:
                    label = page.locator(f"label[for='{radio_id}']")
                    if label.count() > 0:
                        label_text = label.first.inner_text().strip()
                        if not label_text:
                            # Try to find any text in the label
                            label_text = label.evaluate("el => el.textContent").strip()
                        options.append(label_text)
                        option_elements.append(radio)
                        option_labels.append(label)
                    else:
                        # No label found - use the radio value
                        label_text = radio.get_attribute("value") or f"Option {i+1}"
                        options.append(label_text)
                        option_elements.append(radio)
                        option_labels.append(None)
                else:
                    # Try parent for label text
                    parent = radio.locator("xpath=..")
                    if parent.count() > 0:
                        label_text = parent.inner_text().strip()
                        options.append(label_text or f"Option {i+1}")
                        option_elements.append(radio)
                        option_labels.append(None)
                    else:
                        # Fallback
                        options.append(f"Option {i+1}")
                        option_elements.append(radio)
                        option_labels.append(None)
        
        return options, option_elements, option_labels


class RadioGroupProcessor(FieldProcessor):
    """Processor for radio button groups with field label and options."""
    
    def __init__(self, page: Page):
        """Initialize the processor with the page.
        
        Args:
            page: Playwright page
        """
        self.page = page
        self.radio_processor = RadioProcessor()
        
    def process(self, field_element: Locator, answers: Dict[str, Any]) -> bool:
        """Process a radio button group element.
        
        Args:
            field_element: Playwright locator for the radio group fieldset
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        return self.process_radio_group(field_element, answers)
        
    def process_radio_from_group(self, field_label: str, radio_group: Locator, answers: Dict[str, Any]) -> bool:
        """Process a group of radio buttons with the same field label.
        
        Args:
            field_label: The label for the radio group
            radio_group: Playwright locator for the radio group
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # Skip resume-related radio groups
        if field_label.lower().find('resume') >= 0 or field_label.lower().find('cv') >= 0:
            logger.info(f"Skipping resume/CV radio field: '{field_label}'")
            return True
        
        # Get the answer for this field
        answer = get_answer_for_field(answers, field_label)
        
        # Get all the options and their corresponding elements
        options = []
        option_elements = []
        option_labels = []
        
        # Define helper function for radio count determination with proper error handling
        def get_radio_count(rg):
            try:
                if hasattr(rg, 'count'):
                    return rg.count()
                elif isinstance(rg, list):
                    return len(rg)
                else:
                    # Try to convert to list as a last resort
                    try:
                        return len(list(rg))
                    except Exception:
                        logger.error(f"Could not convert radio_group to list")
                        return 0
            except Exception as e:
                logger.error(f"Error getting radio count: {e}")
                return 0
        
        try:
            # Use our helper function to get radio count with proper error handling
            radio_count = get_radio_count(radio_group)
            
            # Extract options and elements
            for i in range(radio_count):
                # Get the radio element
                if hasattr(radio_group, 'nth'):
                    radio = radio_group.nth(i)
                else:
                    radio = radio_group[i]
                    
                radio_id = radio.get_attribute("id")
                option_text = ""
                label_element = None
                
                # First try to get label text from associated label
                if radio_id:
                    label = self.page.locator(f"label[for='{radio_id}']")
                    if label.count() > 0:
                        option_text = label.first.inner_text().strip()
                        label_element = label.first
                
                # If no label text, try radio value
                if not option_text:
                    option_text = radio.get_attribute("value") or f"Option {i+1}"
                
                options.append(option_text)
                option_elements.append(radio)
                option_labels.append(label_element)
            
            # Log what we found
            logger.info(f"Found {len(options)} radio options for '{field_label}': {options}")
            
            # If options are empty, this is likely not a valid radio group
            if not options:
                logger.warning(f"No valid options found for radio group '{field_label}' - skipping")
                return True
                
            # Always ask for user input on every radio question without a stored answer
            # Never auto-select options (per user request)
            if not answer or answer is None:
                # Show options to user
                print(f"\n[APPLICATION FORM] Select an option for: {field_label}")
                for i, option in enumerate(options):
                    print(f"{i+1}. {option}")
                
                # Robust input handling with retry
                while True:
                    try:
                        selection = input(f"Enter option number (1-{len(options)}): ")
                        index = int(selection) - 1
                        if 0 <= index < len(options):
                            # Save the selected answer for future use
                            answers[field_label] = options[index]
                            
                            # Immediately save to disk
                            try:
                                from ..helpers import save_answers
                                import os
                                
                                # Get answers file path from the ApplicationWizard context
                                answers_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'answers', 'default.json')
                                save_answers(answers_file, answers)
                                logger.info(f"Saved new answer for '{field_label}' immediately to disk")
                            except Exception as e:
                                logger.warning(f"Could not immediately save answer for '{field_label}': {e}")
                                
                            # Try to click the selected option
                            try:
                                if option_labels[index] is not None:
                                    option_labels[index].click()
                                    logger.info(f"Selected user-prompted radio option '{options[index]}' (via label) for '{field_label}'")
                                else:
                                    option_elements[index].click()
                                    logger.info(f"Selected user-prompted radio option '{options[index]}' for '{field_label}'")
                                return True
                            except PlaywrightError as e:
                                logger.warning(f"Error clicking user-selected radio: {e}. Trying JS click.")
                                try:
                                    option_elements[index].evaluate("el => el.click()")
                                    logger.info(f"Selected user-prompted radio option '{options[index]}' (via JS) for '{field_label}'")
                                    return True
                                except PlaywrightError as js_e:
                                    logger.error(f"JS click also failed for user selection: {js_e}")
                        else:
                            print(f"Invalid selection. Please enter a number between 1 and {len(options)}.")
                    except (ValueError, KeyboardInterrupt):
                        logger.warning(f"Invalid input or keyboard interrupt for '{field_label}'. No option selected.")
                        # Never auto-select options when no stored answer matches or user doesn't select anything
                        logger.warning(f"No selection made for radio field '{field_label}' - user input required")
                        print(f"\n[APPLICATION FORM] No selection made for '{field_label}'. The field will remain unselected.")
                        return False
            
            # If there is a stored answer, try to find and click the matching option
            else:
                # Find and click the matching option
                selected = False
                for i, option_text in enumerate(options):
                    if answer and (answer.lower() == option_text.lower() or 
                        answer.lower() in option_text.lower() or 
                        option_text.lower() in answer.lower()):
                        try:
                            # Try label click first if available
                            if option_labels[i] is not None:
                                option_labels[i].click()
                                logger.info(f"Selected radio option '{option_text}' (via label) for '{field_label}'")
                            else:
                                option_elements[i].click()
                                logger.info(f"Selected radio option '{option_text}' for '{field_label}'")
                            selected = True
                            break
                        except PlaywrightError as e:
                            logger.warning(f"Error clicking radio: {e}. Trying JS click.")
                            try:
                                option_elements[i].evaluate("el => el.click()")
                                logger.info(f"Selected radio option '{option_text}' (via JS) for '{field_label}'")
                                selected = True
                                break
                            except PlaywrightError as js_e:
                                logger.error(f"JS click also failed: {js_e}")
        
                # If no match found, ask the user to select an option
                if not selected and len(option_elements) > 0:
                    # Show options to user
                    if answer:
                        print(f"\n[APPLICATION FORM] Your stored answer '{answer}' doesn't match any option. Select an option for: {field_label}")
                    else:
                        print(f"\n[APPLICATION FORM] No answer found. Select an option for: {field_label}")
                        
                    for i, option in enumerate(options):
                        print(f"{i+1}. {option}")
                    
                    # Robust input handling with retry
                    while True:
                        try:
                            selection = input(f"Enter option number (1-{len(options)}): ")
                            index = int(selection) - 1
                            if 0 <= index < len(options):
                                # Save the selected answer for future use
                                answers[field_label] = options[index]
                                
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
                                    
                                # Try to click the selected option
                                try:
                                    if option_labels[index] is not None:
                                        option_labels[index].click()
                                        logger.info(f"Selected user-prompted radio option '{options[index]}' (via label) for '{field_label}'")
                                        return True
                                    else:
                                        option_elements[index].click()
                                        logger.info(f"Selected user-prompted radio option '{options[index]}' for '{field_label}'")
                                        return True
                                except PlaywrightError as e:
                                    logger.warning(f"Error clicking user-selected radio: {e}. Trying JS click.")
                                    try:
                                        option_elements[index].evaluate("el => el.click()")
                                        logger.info(f"Selected user-prompted radio option '{options[index]}' (via JS) for '{field_label}'")
                                        return True
                                    except PlaywrightError as js_e:
                                        logger.error(f"JS click also failed for user selection: {js_e}")
                            else:
                                print(f"Invalid selection. Please enter a number between 1 and {len(options)}.")
                        except (ValueError, KeyboardInterrupt):
                            logger.warning(f"Invalid input or keyboard interrupt for '{field_label}'. No option selected.")
                
                # Only indicate no selection if we truly haven't made a selection
                if not selected:
                    logger.warning(f"No selection made for radio field '{field_label}' - user input required")
                    print(f"\n[APPLICATION FORM] No selection made for '{field_label}'. The field will remain unselected.")
                    return False
                return True
        
        except Exception as e:
            logger.error(f"Unexpected error processing radio group '{field_label}': {e}")
            return False
            
        return True
        
    def process_radio_group(self, fieldset: Locator, answers: Dict[str, Any]) -> bool:
        """Process a radio button group in a fieldset.
        
        Args:
            fieldset: Playwright locator for the fieldset
            answers: Dictionary of stored answers
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        # Extract the question from the legend
        legend = fieldset.locator("legend")
        field_label = ""
        
        if legend.count() > 0:
            # Try to get text from spans in the legend
            spans = legend.locator("span")
            if spans.count() > 0:
                for i in range(spans.count()):
                    span_text = spans.nth(i).inner_text().strip()
                    if span_text:
                        field_label = span_text
                        break
            else:
                # Use legend text directly
                field_label = legend.inner_text().strip()
        
        if not field_label:
            logger.warning("Could not determine field label from fieldset")
            # Try to get any text from the fieldset
            field_label = fieldset.inner_text()[:50].strip()
        
        # Extract the radio buttons
        radio_buttons = fieldset.locator("input[type='radio'], div[role='radio']")
        logger.info(f"Processing fieldset radio group: '{field_label}' with {radio_buttons.count()} options")
        
        return self.process_radio_from_group(field_label, radio_buttons, answers)
    
    def group_radio_buttons(self, radio_buttons: Locator) -> Dict[str, List[Locator]]:
        """Group radio buttons by name or container to separate multiple questions.
        
        Args:
            radio_buttons: Playwright locator for all radio buttons
            
        Returns:
            Dict of group name to list of radio buttons
        """
        groups = {}
        
        # Special handling for LinkedIn forms
        # First try to group by name attribute (most reliable method)
        for i in range(radio_buttons.count()):
            radio = radio_buttons.nth(i)
            name = radio.get_attribute("name")
            radio_id = radio.get_attribute("id")
            
            # Debug output for understanding radio button structure
            logger.info(f"Radio button {i+1}: id={radio_id}, name={name}, value={radio.get_attribute('value')}")
            
            if name:
                # Group by name attribute
                if name not in groups:
                    groups[name] = []
                groups[name].append(radio)
            elif radio_id and 'formElement' in radio_id:
                # LinkedIn specific - try to extract form element part to group together
                # Example: urn:li:fsd_formElement:urn:li:jobs_applyformcommon_easyApplyFormElement:(4213350149,18581664356,multipleChoice)-0
                # Extract the part before the trailing digit as the group
                parts = radio_id.split('-')
                if len(parts) > 1 and parts[-1].isdigit():
                    # Use everything before the last dash as the group name
                    group_name = '-'.join(parts[:-1])
                    if group_name not in groups:
                        groups[group_name] = []
                    groups[group_name].append(radio)
                else:
                    # Fallback to using the full ID
                    if radio_id not in groups:
                        groups[radio_id] = []
                    groups[radio_id].append(radio)
            else:
                # Try to find parent element with form-component class
                try:
                    parent = radio.locator("xpath=ancestor::div[contains(@class, 'form-component')][1]")
                    if parent.count() > 0:
                        parent_id = parent.get_attribute("id") or f"form_component_{i}"
                        if parent_id not in groups:
                            groups[parent_id] = []
                        groups[parent_id].append(radio)
                    else:
                        # Last resort - use individual radio
                        individual_id = radio_id or f"unnamed_radio_{i}"
                        groups[individual_id] = [radio]
                except Exception as e:
                    logger.warning(f"Error getting parent for radio button: {e}")
                    # Use individual radio as fallback if all else fails
                    individual_id = radio_id or f"unnamed_radio_{i}"
                    groups[individual_id] = [radio]
        
        # Print debug info about each radio group
        logger.info(f"Grouped {radio_buttons.count()} radio buttons into {len(groups)} groups")
        for group_name, group_radios in groups.items():
            logger.info(f"Group '{group_name}' has {len(group_radios)} radio buttons")
        
        return groups
