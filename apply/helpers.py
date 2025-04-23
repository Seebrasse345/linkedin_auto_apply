"""
Helper functions for the LinkedIn application wizard.
Contains utility functions for processing text and handling data.
"""
import re
import os
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def load_answers(answers_file: str) -> Dict[str, Any]:
    """Load answers from the specified JSON file."""
    if os.path.exists(answers_file):
        try:
            with open(answers_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error loading answers file: {e}")
            return {}
    return {}

def save_answers(answers_file: str, answers: Dict[str, Any]) -> None:
    """Save updated answers back to the JSON file."""
    os.makedirs(os.path.dirname(answers_file), exist_ok=True)
    try:
        with open(answers_file, 'w') as f:
            json.dump(answers, f, indent=2)
        logger.info(f"Answers saved to {answers_file}")
    except Exception as e:
        logger.error(f"Error saving answers: {e}")

def save_application_result(data_dir: str, job_id: str, success: bool) -> None:
    """Save application result to a JSON file. Concatenates with existing results."""
    result_type = "successful" if success else "failed"
    filename = f"{result_type}_applications.json"
    filepath = os.path.join(data_dir, filename)
    
    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    
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

def should_auto_answer(field_label: str, options: List[str]) -> bool:
    """Determine if we should auto-answer this question instead of prompting."""
    # Always ask the user for input, no auto-answering
    # This ensures the user is in control of their application answers
    logger.info(f"Will ask user for input on question: '{field_label}'")
    return False

def get_auto_answer(field_label: str, options: List[str]) -> str:
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

def get_answer_for_field(answers: Dict[str, Any], field_label: str) -> Optional[str]:
    """Get the answer for a field from the answers dictionary."""
    # Normalize the label by removing special characters and converting to lowercase
    normalized_label = re.sub(r'[^a-zA-Z0-9\s]', '', field_label).lower()
    
    # Try exact match first
    if field_label in answers:
        return answers[field_label]
    
    # Try case-insensitive match
    for key, value in answers.items():
        if key.lower() == field_label.lower():
            return value
    
    # Try partial match (field label contains answer key or vice versa)
    for key, value in answers.items():
        if (key.lower() in normalized_label or 
            normalized_label in key.lower() or
            any(word in normalized_label for word in key.lower().split() if len(word) > 3)):
            return value
    
    # Try generic keywords
    keywords = {
        "phone": answers.get("Mobile phone number", ""),
        "location": answers.get("Location (city)", ""),
        "experience": answers.get("How many years*experience", ""),
        "salary": answers.get("Salary expectation", ""),
        "gender": answers.get("gender", ""),
        "ethnicity": answers.get("ethnicity", ""),
        "disability": answers.get("disability", {}).get("status", "")
    }
    
    for keyword, answer in keywords.items():
        if keyword in normalized_label and answer:
            return answer
            
    return None
