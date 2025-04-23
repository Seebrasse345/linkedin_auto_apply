import json
import os
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from playwright.sync_api import Page, TimeoutError, Error as PlaywrightError

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

class ApplicationWizard:
    def __init__(self, page, answers_file='answers/default.json'):
        self.page = page
        self.answers_file = answers_file
        self.successful_applications = []
        self.failed_applications = []
        self.answers = self._load_answers()
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
    def _load_answers(self) -> Dict[str, Any]:
        """Load answers from the specified JSON file."""
        if os.path.exists(self.answers_file):
            try:
                with open(self.answers_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error loading answers file: {e}")
                return {}
        return {}
    
    def _save_answers(self) -> None:
        """Save updated answers back to the JSON file."""
        os.makedirs(os.path.dirname(self.answers_file), exist_ok=True)
        try:
            with open(self.answers_file, 'w') as f:
                json.dump(self.answers, f, indent=2)
            logger.info(f"Answers saved to {self.answers_file}")
        except Exception as e:
            logger.error(f"Error saving answers: {e}")
    
    def _save_application_result(self, job_id: str, success: bool) -> None:
        """Save application result to a JSON file. Concatenates with existing results."""
        result_type = "successful" if success else "failed"
        filename = f"{result_type}_applications.json"
        filepath = os.path.join(self.data_dir, filename)
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load existing results or create new list
        existing_results = []
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as file:
                    existing_results = json.load(file)
                    if not isinstance(existing_results, list):
                        existing_results = []
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading existing {result_type} applications: {e}. Creating new file.")
            existing_results = []
        
        # Add new result and save
        if job_id not in existing_results:
            existing_results.append(job_id)
            
            with open(filepath, 'w') as file:
                json.dump(existing_results, file)
            
            logger.info(f"Updated {result_type} applications list with Job ID: {job_id} (total: {len(existing_results)})")
        else:
            logger.info(f"Job ID: {job_id} already in {result_type} applications list")
            
    def _get_field_label(self, field_element) -> str:
        """Extract the label text for a form field."""
        # Try to get label via for attribute
        field_id = field_element.get_attribute("id")
        if field_id:
            label = self.page.locator(f"label[for='{field_id}']")
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
        
        return ""    # If all else fails, return a placeholder with the field type
        field_type = field_element.get_attribute("type") or "field"
        return f"Unlabeled {field_type}"
    
    def _get_answer_for_field(self, field_label: str) -> Optional[str]:
        """Get the answer for a field from the answers dictionary."""
        # Normalize the label by removing special characters and converting to lowercase
        normalized_label = re.sub(r'[^a-zA-Z0-9\s]', '', field_label).lower()
        
        # Try exact match first
        if field_label in self.answers:
            return self.answers[field_label]
        
        # Try case-insensitive match
        for key, value in self.answers.items():
            if key.lower() == field_label.lower():
                return value
        
        # Try partial match (field label contains answer key or vice versa)
        for key, value in self.answers.items():
            if (key.lower() in normalized_label or 
                normalized_label in key.lower() or
                any(word in normalized_label for word in key.lower().split() if len(word) > 3)):
                return value
        
        # Try generic keywords
        keywords = {
            "phone": self.answers.get("Mobile phone number", ""),
            "location": self.answers.get("Location (city)", ""),
            "experience": self.answers.get("How many years*experience", ""),
            "salary": self.answers.get("Salary expectation", ""),
            "gender": self.answers.get("gender", ""),
            "ethnicity": self.answers.get("ethnicity", ""),
            "disability": self.answers.get("disability", {}).get("status", "")
        }
        
        for keyword, answer in keywords.items():
            if keyword in normalized_label and answer:
                return answer
                
        return None
    
    def _ask_for_input(self, field_label: str, field_type: str) -> str:
        """Ask the user for input when an answer is not available."""
        print(f"\n[APPLICATION FORM] Need input for: {field_label} (Type: {field_type})")
        user_input = input("Please provide an answer: ")
        
        # Save the answer for future use
        self.answers[field_label] = user_input
        self._save_answers()
        
        return user_input
    
    def _process_text_input(self, input_element) -> bool:
        """Process a text input field."""
        field_label = self._get_field_label(input_element)
        answer = self._get_answer_for_field(field_label)
        
        if not answer:
            answer = self._ask_for_input(field_label, "text")
        
        try:
            input_element.fill(answer)
            logger.info(f"Filled text input '{field_label}' with answer")
            return True
        except PlaywrightError as e:
            logger.error(f"Error filling text input '{field_label}': {e}")
            return False
    
    def _process_textarea(self, textarea_element) -> bool:
        """Process a textarea field."""
        field_label = self._get_field_label(textarea_element)
        answer = self._get_answer_for_field(field_label)
        
        if not answer:
            answer = self._ask_for_input(field_label, "textarea")
        
        try:
            textarea_element.fill(answer)
            logger.info(f"Filled textarea '{field_label}' with answer")
            return True
        except PlaywrightError as e:
            logger.error(f"Error filling textarea '{field_label}': {e}")
            return False
    
    def _process_select(self, select_element) -> bool:
        """Process a select dropdown field."""
        field_label = self._get_field_label(select_element)
        answer = self._get_answer_for_field(field_label)
        
        try:
            # Get available options
            options = []
            for option in select_element.locator("option").all():
                option_text = option.inner_text().strip()
                if option_text and option_text != "Select an option":
                    options.append(option_text)
            
            if not options:
                logger.warning(f"No options found for select '{field_label}'")
                return False
            
            if not answer:
                # Show options to user
                print(f"\n[APPLICATION FORM] Select an option for: {field_label}")
                for i, option in enumerate(options):
                    print(f"{i+1}. {option}")
                
                selection = input(f"Enter option number (1-{len(options)}): ")
                try:
                    index = int(selection) - 1
                    if 0 <= index < len(options):
                        answer = options[index]
                    else:
                        answer = options[0]  # Default to first option
                except ValueError:
                    answer = options[0]  # Default to first option
                
                # Save the answer
                self.answers[field_label] = answer
                self._save_answers()
            
            # Try to select by value or label
            if answer in options:
                select_element.select_option(label=answer)
                logger.info(f"Selected option '{answer}' for '{field_label}'")
                return True
            else:
                # Try to find closest match
                closest_match = next((opt for opt in options if answer.lower() in opt.lower()), options[0])
                select_element.select_option(label=closest_match)
                logger.info(f"Selected closest matching option '{closest_match}' for '{field_label}'")
                return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing select '{field_label}': {e}")
            return False
    
    def _process_radio(self, radio_group) -> bool:
        """Process a radio button group."""
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
            field_label = self._get_field_label(radio_group.first)
        
        logger.info(f"Processing radio group: '{field_label}'")
        answer = self._get_answer_for_field(field_label)
        
        try:
            # Get available options
            options = []
            option_elements = []
            option_labels = []
            
            # Try to find labels associated with the radio buttons
            for i, radio in enumerate(radio_group.all()):
                radio_html = radio.evaluate("el => el.outerHTML")
                radio_id = radio.get_attribute("id")
                
                if "role='radio'" in radio_html or radio.get_attribute("role") == "radio":
                    # Modern LinkedIn UI uses div with role="radio"
                    label_text = radio.inner_text().strip()
                    if not label_text and radio_id:
                        label = self.page.locator(f"label[for='{radio_id}']")
                        if label.count() > 0:
                            label_text = label.first.inner_text().strip()
                    options.append(label_text)
                    option_elements.append(radio)
                    option_labels.append(None)  # No separate label element
                elif radio.get_attribute("type") == "radio":
                    # Traditional radio buttons
                    if radio_id:
                        label = self.page.locator(f"label[for='{radio_id}']")
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
                            options.append(label_text)
                            option_elements.append(radio)
                            option_labels.append(None)
            
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
                            first_label = self.page.locator(f"label[for='{first_id}']")
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
                        try:
                            # First try to click the label if available
                            if option_labels[answer_index] is not None and option_labels[answer_index].count() > 0:
                                option_labels[answer_index].click()
                                logger.info(f"Selected '{answer_text}' (via label) for question: '{field_label}'")
                                return True
                            
                            # Then try regular click on the radio
                            option_elements[answer_index].click()
                            logger.info(f"Selected '{answer_text}' for question: '{field_label}'")
                            return True
                        except PlaywrightError as e:
                            logger.warning(f"Error clicking radio option: {e}. Trying JavaScript click.")
                            try:
                                option_elements[answer_index].evaluate("el => el.click()")
                                logger.info(f"Selected '{answer_text}' (via JS) for question: '{field_label}'")
                                return True
                            except PlaywrightError as js_e:
                                logger.error(f"JS click also failed: {js_e}")
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
                    # First try to click the label if available (more reliable)
                    try:
                        if option_labels[selected_index] is not None and option_labels[selected_index].count() > 0:
                            option_labels[selected_index].click()
                            logger.info(f"Auto-selected option '{options[selected_index]}' (via label) for '{field_label}'")
                        else:
                            option_elements[selected_index].click()
                            logger.info(f"Auto-selected option '{options[selected_index]}' for '{field_label}'")
                        
                        # Save this answer for future use
                        self.answers[field_label] = options[selected_index]
                        self._save_answers()
                        return True
                    except PlaywrightError as e:
                        logger.warning(f"Error with regular click: {e}. Trying JavaScript click.")
                        try:
                            # Try JS click as a fallback
                            option_elements[selected_index].evaluate("el => el.click()")
                            logger.info(f"Auto-selected option '{options[selected_index]}' (via JS) for '{field_label}'")
                            
                            # Save this answer for future use
                            self.answers[field_label] = options[selected_index]
                            self._save_answers()
                            return True
                        except PlaywrightError as js_e:
                            logger.error(f"JS click also failed: {js_e}")
                            return False
            
            # Try to find exact or similar match for stored answer
            selected = False
            for i, option_text in enumerate(options):
                if (answer.lower() == option_text.lower() or 
                    answer.lower() in option_text.lower() or 
                    option_text.lower() in answer.lower()):
                    try:
                        # First try label click if available
                        if option_labels[i] is not None and option_labels[i].count() > 0:
                            option_labels[i].click()
                            logger.info(f"Selected radio option '{option_text}' (via label) for '{field_label}'")
                        else:
                            option_elements[i].click()
                            logger.info(f"Selected radio option '{option_text}' for '{field_label}'")
                        selected = True
                        break
                    except PlaywrightError as e:
                        logger.warning(f"Error with regular click: {e}. Trying JavaScript click.")
                        try:
                            option_elements[i].evaluate("el => el.click()")
                            logger.info(f"Selected radio option '{option_text}' (via JS) for '{field_label}'")
                            selected = True
                            break
                        except PlaywrightError:
                            continue  # Try the next option
            
            # If no match, select first option
            if not selected and option_elements and len(option_elements) > 0:
                try:
                    # First try label click if available
                    if option_labels[0] is not None and option_labels[0].count() > 0:
                        option_labels[0].click()
                        logger.info(f"Selected first radio option '{options[0]}' (via label) for '{field_label}'")
                    else:
                        option_elements[0].click()
                        logger.info(f"Selected first radio option '{options[0]}' for '{field_label}'")
                except PlaywrightError as e:
                    logger.warning(f"Error with regular click: {e}. Trying JavaScript click.")
                    try:
                        option_elements[0].evaluate("el => el.click()")
                        logger.info(f"Selected first radio option '{options[0]}' (via JS) for '{field_label}'")
                    except PlaywrightError as js_e:
                        logger.error(f"JS click also failed: {js_e}")
                        return False
            
            return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing radio group '{field_label}': {e}")
            return False
    
    def _process_checkbox(self, checkbox_group) -> bool:
        """Process a checkbox group."""
        # Similar approach as radio buttons, but multiple can be selected
        container = checkbox_group.first.locator("xpath=ancestor::div[contains(@class, 'form-component')][1]")
        field_label = ""
        
        if container.count() > 0:
            heading = container.locator("h3, h4, .fb-form-element-label")
            if heading.count() > 0:
                field_label = heading.first.inner_text().strip()
        
        if not field_label:
            field_label = self._get_field_label(checkbox_group.first)
        
        answer = self._get_answer_for_field(field_label)
        
        try:
            # For simplicity, we'll just select the first checkbox if no specific answer
            if not answer or answer.lower() in ["yes", "true", "1"]:
                checkbox_group.first.check() if "type='checkbox'" in checkbox_group.first.evaluate("el => el.outerHTML") else checkbox_group.first.click()
                logger.info(f"Checked first checkbox for '{field_label}'")
            else:
                # Uncheck if answer is explicitly "no"
                if answer.lower() in ["no", "false", "0"]:
                    if checkbox_group.first.is_checked():
                        checkbox_group.first.uncheck() if "type='checkbox'" in checkbox_group.first.evaluate("el => el.outerHTML") else checkbox_group.first.click()
                        logger.info(f"Unchecked checkbox for '{field_label}'")
            
            return True
                
        except PlaywrightError as e:
            logger.error(f"Error processing checkbox '{field_label}': {e}")
            return False
    
    def _process_resume(self) -> bool:
        """Skip resume selection - leave the default resume as is."""
        # First check if resume selector is present
        resume_elements = self.page.locator(RESUME_SELECTOR)
        
        if resume_elements.count() > 0:
            logger.info("Resume selector found but skipping selection as per user request")
        
        # Check for radio buttons related to resume selection - just log but don't interact
        resume_radios = self.page.locator('input[type="radio"][name*="resume"], div[role="radio"][aria-label*="resume"]')
        if resume_radios.count() > 0:
            logger.info(f"Found {resume_radios.count()} resume radio buttons but skipping selection")
        
        # Simply return true without changing anything
        return True
        
    def _group_radio_buttons(self, radio_buttons) -> Dict[str, List[Any]]:
        """Group radio buttons by name or container to separate multiple questions."""
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
    
    def _process_radio_group(self, fieldset) -> bool:
        """Process a radio button group in a fieldset."""
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
        
        return self._process_radio_from_group(field_label, radio_buttons)
    
    def _process_radio_from_group(self, field_label: str, radio_group) -> bool:
        """Process a group of radio buttons with the same field label."""
        # Skip resume-related radio groups
        if field_label.lower().find('resume') >= 0 or field_label.lower().find('cv') >= 0:
            logger.info(f"Skipping resume/CV radio field: '{field_label}'")
            return True
        
        # Get the answer for this field
        answer = self._get_answer_for_field(field_label)
        
        # Get all the options and their corresponding elements
        options = []
        option_elements = []
        option_labels = []
        
        try:
            # Handle both locator arrays and regular python lists
            # Handle both Playwright locator arrays and regular Python lists
            try:
                if hasattr(radio_group, 'count'):
                    radio_count = radio_group.count()
                else:
                    radio_count = len(radio_group)
            except Exception as e:
                logger.error(f"Error getting radio count: {e}")
                radio_count = 0
            
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
                
            # If no answer is stored, prompt the user
            if not answer:
                # Check for common yes/no patterns before prompting
                if self._should_auto_answer(field_label, options):
                    auto_answer = self._get_auto_answer(field_label, options)
                    logger.info(f"Using auto-answer '{auto_answer}' for '{field_label}'")
                    answer = auto_answer
                else:
                    # Show options to user
                    print(f"\n[APPLICATION FORM] Select an option for: {field_label}")
                    for i, option in enumerate(options):
                        print(f"{i+1}. {option}")
                    
                    try:
                        selection = input(f"Enter option number (1-{len(options)}): ")
                        index = int(selection) - 1
                        if 0 <= index < len(options):
                            answer = options[index]
                        else:
                            answer = options[0]  # Default to first option
                    except (ValueError, KeyboardInterrupt):
                        answer = options[0]  # Default to first option
                    
                    # Save this answer for future use
                    self.answers[field_label] = answer
                    self._save_answers()
            
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
            
            # If no match found, select first option
            if not selected and len(option_elements) > 0:
                try:
                    if option_labels[0] is not None:
                        option_labels[0].click()
                        logger.info(f"Selected first radio option '{options[0]}' (via label) for '{field_label}'")
                    else:
                        option_elements[0].click()
                        logger.info(f"Selected first radio option '{options[0]}' for '{field_label}'")
                except PlaywrightError as e:
                    logger.warning(f"Error clicking first radio: {e}. Trying JS click.")
                    try:
                        option_elements[0].evaluate("el => el.click()")
                        logger.info(f"Selected first radio option '{options[0]}' (via JS) for '{field_label}'")
                    except PlaywrightError as js_e:
                        logger.error(f"JS click also failed: {js_e}")
                        return False
            
            return True
        except PlaywrightError as e:
            logger.error(f"Error processing radio group '{field_label}': {e}")
            return False
    
    def _should_auto_answer(self, field_label: str, options: List[str]) -> bool:
        """Determine if we should auto-answer this question instead of prompting."""
        # IMPORTANT: Education and degree questions should always prompt the user
        # These are critical qualifications that need human input
        if any(kw in field_label.lower() for kw in ['degree', 'education', 'bachelor', 'master', 'phd', 'diploma']):
            logger.info(f"Education-related question will prompt for user input: '{field_label}'")
            return False
        
        # Check if it's a simple yes/no question
        if len(options) == 2 and any('yes' in opt.lower() for opt in options) and any('no' in opt.lower() for opt in options):
            # Auto-answer yes/no for common questions
            if any(kw in field_label.lower() for kw in ['disability', 'commut', 'locat', 'relocat', 
                                                      'experience', 'work', 'skill', 'qualified', 
                                                      'eligible']):
                return True
        
        # Auto-answer for gender, ethnicity, veteran status
        if any(kw in field_label.lower() for kw in ['gender', 'sex', 'ethnicity', 'race', 'veteran', 'military']):
            return True
            
        # Ask the user for anything not specifically categorized
        return False
    
    def _get_auto_answer(self, field_label: str, options: List[str]) -> str:
        """Get an auto-generated answer based on field type and options."""
        # Handles common yes/no questions
        if len(options) == 2 and 'yes' in options[0].lower() and 'no' in options[1].lower():
            # For disability questions, prefer "No"
            if 'disability' in field_label.lower() or 'disabled' in field_label.lower():
                return "No"
            # For experience or qualification questions, prefer "Yes"
            elif any(kw in field_label.lower() for kw in ['experience', 'work', 'skill', 'qualified', 'eligible']):
                return "Yes"
            # For location/commute questions, prefer "Yes"
            elif any(kw in field_label.lower() for kw in ['commut', 'locat', 'relocat', 'move', 'travel']):
                return "Yes"
            # For education questions, prefer "Yes" (having the degree is better than not)
            elif any(kw in field_label.lower() for kw in ['degree', 'education', 'bachelor', 'master']):
                return "Yes"
        
        # For demographic questions
        if 'gender' in field_label.lower() or 'sex' in field_label.lower():
            # Look for "prefer not to say"
            for option in options:
                if 'prefer not' in option.lower():
                    return option
        
        if 'ethnicity' in field_label.lower() or 'race' in field_label.lower():
            # Look for "prefer not to say" first, then "white"
            for option in options:
                if 'prefer not' in option.lower():
                    return option
            for option in options:
                if 'white' in option.lower():
                    return option
        
        if 'veteran' in field_label.lower() or 'military' in field_label.lower():
            # Default to "No" for veteran status
            for option in options:
                if option.lower() == 'no':
                    return option
        
        # Default to first option if no special case
        return options[0] if options else ""
        
    def _process_form_fields(self) -> bool:
        """Process all form fields on the current step."""
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
                if not self._process_text_input(text_inputs.nth(i)):
                    success = False
            
            textareas = app_modal.locator("textarea:visible")
            logger.info(f"Found {textareas.count()} textarea fields in form")
            
            for i in range(textareas.count()):
                if not self._process_textarea(textareas.nth(i)):
                    success = False
            
            selects = app_modal.locator("select:visible")
            logger.info(f"Found {selects.count()} select fields in form")
            
            for i in range(selects.count()):
                if not self._process_select(selects.nth(i)):
                    success = False
            
            # Find all fieldsets that contain radio buttons - these are separate question groups
            radio_fieldsets = app_modal.locator("fieldset:has(input[type='radio']), fieldset:has(div[role='radio'])")
            if radio_fieldsets.count() > 0:
                logger.info(f"Found {radio_fieldsets.count()} radio button groups/fieldsets in form")
                
                # Process each fieldset as a separate radio button group
                for i in range(radio_fieldsets.count()):
                    fieldset = radio_fieldsets.nth(i)
                    if not self._process_radio_group(fieldset):
                        success = False
            else:
                # Fallback for radio buttons not in fieldsets
                radio_buttons = app_modal.locator("input[type='radio'], div[role='radio']")
                logger.info(f"Found {radio_buttons.count()} individual radio buttons in form")
                
                if radio_buttons.count() > 0:
                    # Try to group by name attribute or parent container
                    grouped_radios = self._group_radio_buttons(radio_buttons)
                    for group_name, group_elements in grouped_radios.items():
                        logger.info(f"Processing radio group '{group_name}' with {len(group_elements)} options")
                        if not self._process_radio_from_group(group_name, group_elements):
                            success = False
            
            checkbox_groups = app_modal.locator("input[type='checkbox']:visible, div[role='checkbox']:visible")
            logger.info(f"Found {checkbox_groups.count()} checkbox fields in form")
            
            if checkbox_groups.count() > 0:
                if not self._process_checkbox(checkbox_groups):
                    success = False
            
            # Process resume selector if present
            if not self._process_resume():
                success = False
            
            return success
            
        except PlaywrightError as e:
            logger.error(f"Error processing form fields: {e}")
            success = False
        
        return success
    
    def start_application(self, job_data: Dict[str, str]) -> str:
        """Start the application process for a job."""
        logger.info(f"Starting application for job: {job_data.get('title', 'Unknown')}")

        try:
            # Check if job_data contains a flag indicating the Easy Apply button was already clicked
            if job_data.get('easy_apply_clicked', False):
                logger.info("Easy Apply button was already clicked, proceeding with application")
                # No need to click again, just wait for the form to load
                self.page.wait_for_timeout(1000)            
            else:
                # Check if we can find an Easy Apply button
                easy_apply_button = self.page.locator(EASY_APPLY_BUTTON_SELECTOR)
                if easy_apply_button.count() == 0:
                    logger.warning("No Easy Apply button found")
                    self.failed_applications.append({
                        "job": job_data,
                        "reason": "No Easy Apply button found",
                        "timestamp": datetime.now().isoformat()
                    })
                    return APPLICATION_FAILURE

                # Click the Easy Apply button (use first() to handle multiple matches)
                logger.info("Clicking Easy Apply button")
                easy_apply_button.first.click()
                self.page.wait_for_timeout(1500)  # Wait for the form to load (reduced from 2000ms)

            # Process the application form steps
            step_count = 0
            max_steps = 15  # Safety limit
            previous_form_content = None  # Track previous form content to detect loops
            duplicate_form_count = 0  # Count how many times we see the same form
            max_duplicates = 3  # Maximum number of times to try the same form before giving up

            while step_count < max_steps:
                logger.info(f"Processing application step {step_count + 1}")

                # Locate the application modal
                modal = self.page.locator(APPLICATION_MODAL_SELECTOR)
                if modal.count() == 0:
                    logger.warning("Application modal not found during navigation")
                    self.failed_applications.append({
                        "job": job_data,
                        "reason": f"Application modal disappeared at step {step_count + 1}",
                        "timestamp": datetime.now().isoformat()
                    })
                    self._save_application_data()
                    return APPLICATION_FAILURE

                app_modal = modal.first

                # Check if we're in a loop by comparing form content with previous step
                current_form_content = app_modal.inner_html()
                if current_form_content == previous_form_content:
                    duplicate_form_count += 1
                    logger.warning(f"Detected same form content in consecutive steps ({duplicate_form_count}/{max_duplicates})")
                    
                    if duplicate_form_count >= max_duplicates:
                        logger.error(f"Detected infinite loop in application form - same form appeared {max_duplicates} times")

                        # Try a different approach - click a different next button if available
                        all_buttons = app_modal.locator("button")
                        found_alternative = False

                        for i in range(all_buttons.count()):
                            button = all_buttons.nth(i)
                            button_text = button.inner_text().lower()
                            if any(word in button_text for word in ["next", "continue", "submit", "review"]):
                                if i > 0:  # Not the first button we've been clicking
                                    logger.info(f"Trying alternative button with text: {button_text}")
                                    button.click()
                                    self.page.wait_for_timeout(2000)
                                    found_alternative = True
                                    break

                        if not found_alternative:
                            # Take a debug screenshot
                            try:
                                debug_dir = os.path.join(self.data_dir, 'debug')
                                os.makedirs(debug_dir, exist_ok=True)
                                screenshot_path = os.path.join(debug_dir, f"form_loop_{step_count+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                                self.page.screenshot(path=screenshot_path)
                                logger.info(f"Saved debug screenshot to {screenshot_path}")
                            except Exception as e:
                                logger.error(f"Failed to save debug screenshot: {e}")
                                
                            self.failed_applications.append({
                                "job": job_data,
                                "reason": f"Infinite loop detected in application form at step {step_count + 1}",
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_FAILURE
                else:
                    # Reset the counter if form content changed
                    duplicate_form_count = 0
                    previous_form_content = current_form_content

                # Process form fields on current step
                if not self._process_form_fields():
                    logger.warning(f"Some fields could not be processed on step {step_count + 1}")

                self.page.wait_for_timeout(800)  # Wait for fields to be filled (reduced from 1000ms)

                # Check for Submit button within the modal
                submit_button = app_modal.locator("button[aria-label='Submit application'], button:has-text('Submit application')")
                if submit_button.count() > 0:
                    logger.info("Found Submit button - this is the final step")
                    try:
                        # Use evaluate to force a click (more reliable than regular click)
                        submit_button.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for submission

                        # Check for Done button - may be in a new modal (check both in modal and whole page)
                        # First check in current modal if it still exists
                        if modal.count() > 0:
                            done_in_modal = app_modal.locator("button[aria-label='Done'], button[aria-label='Dismiss'], button:has-text('Done'), button:has-text('Dismiss')")
                            if done_in_modal.count() > 0:
                                logger.info("Found Done button in current modal - application completed successfully")
                                done_in_modal.first.evaluate("button => button.click()")
                                self.page.wait_for_timeout(1000)

                                # Record successful application
                                self.successful_applications.append({
                                    "job": job_data,
                                    "timestamp": datetime.now().isoformat()
                                })
                                self._save_application_data()
                                return APPLICATION_SUCCESS

                        # If not found in modal, check whole page (may be in a different modal)
                        done_button = self.page.locator("button[aria-label='Done'], button[aria-label='Dismiss'], button:has-text('Done'), button:has-text('Dismiss')")
                        if done_button.count() > 0:
                            logger.info("Found Done button in new modal - application completed successfully")
                            done_button.first.evaluate("button => button.click()")
                            self.page.wait_for_timeout(1000)

                            # Record successful application
                            self.successful_applications.append({
                                "job": job_data,
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_SUCCESS
                        else:
                            logger.warning("Did not find Done button after submission")
                            self.failed_applications.append({
                                "job": job_data,
                                "reason": "No Done button after submission",
                                "timestamp": datetime.now().isoformat()
                            })
                            self._save_application_data()
                            return APPLICATION_FAILURE
                    except PlaywrightError as e:
                        logger.error(f"Error clicking Submit button: {e}")
                        self.failed_applications.append({
                            "job": job_data,
                            "reason": f"Error clicking Submit button: {e}",
                            "timestamp": datetime.now().isoformat()
                        })
                        self._save_application_data()
                        return APPLICATION_FAILURE

                # Check for Next button within the modal - using much more specific selectors
                # For debugging - check what buttons exist in the form
                all_form_buttons = app_modal.locator("button")
                logger.info(f"Found {all_form_buttons.count()} total buttons in the form")
                
                # Debug: Output all button text for analysis
                for i in range(min(all_form_buttons.count(), 5)):  # Limit to first 5 to avoid spam
                    try:
                        button = all_form_buttons.nth(i)
                        button_text = button.inner_text().strip()
                        button_attrs = {}
                        for attr in ['aria-label', 'id', 'data-easy-apply-next-button', 'class']:
                            value = button.get_attribute(attr)
                            if value:
                                button_attrs[attr] = value
                        logger.info(f"Button {i+1} text: '{button_text}', attributes: {button_attrs}")
                    except PlaywrightError:
                        pass
                
                # First try the most specific button - data-easy-apply-next-button (this is the official LinkedIn attribute)
                next_with_attr = app_modal.locator("[data-easy-apply-next-button]")
                logger.info(f"Found {next_with_attr.count()} buttons with data-easy-apply-next-button attribute")
                if next_with_attr.count() > 0:
                    logger.info("Using official LinkedIn next button with data-easy-apply-next-button attribute")
                    try:
                        next_with_attr.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking official next button: {e}, will try alternatives")

                # Then try to find the specific footer Next button
                footer_next = app_modal.locator("footer button:has-text('Next')")
                logger.info(f"Found {footer_next.count()} footer Next buttons")
                if footer_next.count() > 0:
                    # This is the most reliable button - in the footer of the form
                    logger.info("Found Next button in form footer - clicking it")
                    try:
                        # Use evaluate to force a click (more reliable than regular click)
                        footer_next.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)  # Wait for next step to load
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking footer Next button: {e}, will try alternatives")

                # Try other specific button selectors
                specific_next = app_modal.locator("button[aria-label='Continue to next step'], button[aria-label='Review your application']")
                if specific_next.count() > 0:
                    logger.info("Found specific Next button with aria-label - clicking it")
                    try:
                        specific_next.first.evaluate("button => button.click()")
                        self.page.wait_for_timeout(1500)
                        step_count += 1
                        continue
                    except PlaywrightError as e:
                        logger.warning(f"Error clicking specific Next button: {e}, will try alternatives")

                # Last resort - try any button with appropriate text
                fallback_next = app_modal.locator("button:has-text('Next'), button:has-text('Continue'), button:has-text('Review')")
                if fallback_next.count() > 0:
                    logger.info("Using fallback: Found any button with Next/Continue/Review text")
                    try:
                        # Try each button until one works
                        clicked = False
                        for i in range(fallback_next.count()):
                            button = fallback_next.nth(i)
                            try:
                                button_text = button.inner_text().strip()
                                logger.info(f"Trying to click button with text: '{button_text}'")
                                button.evaluate("button => button.click()")
                                clicked = True
                                self.page.wait_for_timeout(1500)
                                break
                            except PlaywrightError:
                                continue

                        if clicked:
                            step_count += 1
                            continue
                    except PlaywrightError as e:
                        logger.warning(f"Error with fallback buttons: {e}")
                    else:
                        logger.warning("No Next button found - application flow broken")
                        # Take a screenshot of the current state for debugging
                        try:
                            debug_dir = os.path.join(self.data_dir, 'debug')
                            os.makedirs(debug_dir, exist_ok=True)
                            screenshot_path = os.path.join(debug_dir, f"failed_step_{step_count+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                            self.page.screenshot(path=screenshot_path)
                            logger.info(f"Saved debug screenshot to {screenshot_path}")
                        except Exception as e:
                            logger.error(f"Failed to save debug screenshot: {e}")
                            
                        # Record the failed application
                        self._save_application_result(job_data.get('id', 'unknown'), False)
                        return APPLICATION_FAILURE
            
            logger.warning(f"Reached maximum steps limit ({max_steps})")
            # Record the failed application
            self._save_application_result(job_data.get('id', 'unknown'), False)
            return APPLICATION_INCOMPLETE
            
        except TimeoutError as e:
            logger.error(f"Timeout during application process: {e}")
            # Record the failed application
            self._save_application_result(job_data.get('id', 'unknown'), False)
            return APPLICATION_FAILURE
        except PlaywrightError as e:
            logger.error(f"Playwright error during application process: {e}")
            # Record the failed application
            self._save_application_result(job_data.get('id', 'unknown'), False)
            return APPLICATION_FAILURE
        except Exception as e:
            logger.error(f"Unexpected error during application process: {e}")
            # Record the failed application
            self._save_application_result(job_data.get('id', 'unknown'), False)
            return APPLICATION_FAILURE