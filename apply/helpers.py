"""
Helper functions for the LinkedIn application wizard.
Contains utility functions for processing text and handling data.
"""
import re
import os
import json
import logging
from datetime import datetime
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


def save_job_description(data_dir: str, job_data: dict) -> None:
    """Save job description to a JSON file for successful applications.
    
    Args:
        data_dir: Directory to save the job descriptions file
        job_data: Job data containing title, company, and description
    """
    filename = "job_descriptions_applied.json"
    filepath = os.path.join(data_dir, filename)
    
    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    
    # Extract relevant job information
    job_id = job_data.get("job_id", job_data.get("id", "unknown"))
    job_title = job_data.get("title", "Unknown Title")
    job_company = job_data.get("company", "Unknown Company")
    job_description = job_data.get("description", "")
    
    # Prepare the entry to save
    job_entry = {
        "job_id": job_id,
        "title": job_title,
        "company": job_company,
        "description": job_description,
        "timestamp": datetime.now().isoformat()
    }
    
    # Load existing entries or create new list
    existing_entries = []
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                existing_entries = json.load(file)
                if not isinstance(existing_entries, list):
                    existing_entries = []
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error loading existing job descriptions: {e}. Creating new file.")
        existing_entries = []
    
    # Check if job ID already exists in the list
    job_ids = [entry.get("job_id") for entry in existing_entries]
    
    # Add new entry only if job ID is not already in the list
    if job_id not in job_ids:
        existing_entries.append(job_entry)
        
        with open(filepath, 'w') as file:
            json.dump(existing_entries, file, indent=2)
        
        logger.info(f"Saved job description for {job_title} at {job_company} (ID: {job_id})")
    else:
        logger.info(f"Job description for ID: {job_id} already saved")

def should_auto_answer(field_label: str, options: List[str]) -> bool:
    """Determine if we should auto-answer this question instead of prompting."""
    # Auto-answer for any years of experience questions
    if ('years of experience' in field_label.lower() or 'years of work experience' in field_label.lower() 
            or 'how many years' in field_label.lower()):
        logger.info(f"Will auto-answer experience question with default value: '{field_label}'")
        return True
    
    # For all other questions, always prompt the user
    logger.info(f"Will ask user for input on question: '{field_label}'")
    return False


def get_stored_answers() -> Dict[str, Any]:
    """Get all stored answers from the default answers file."""
    answers_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'answers', 'default.json')
    return load_answers(answers_file)

def get_auto_answer(field_label: str, options: List[str]) -> str:
    """Get an auto-generated answer based on field type and options."""
    # Always answer '2' for any years of experience questions
    field_lower = field_label.lower()
    if ('years of experience' in field_lower or 'years of work experience' in field_lower
            or 'how many years' in field_lower):
        logger.info(f"Auto-answering years of experience question with '2': {field_label}")
        return "2"
    
    # Handles common yes/no questions
    if len(options) == 2 and 'yes' in options[0].lower() and 'no' in options[1].lower():
        # For disability questions, prefer "No"
        if 'disability' in field_lower or 'disabled' in field_lower:
            return "No"
        # For experience or qualification questions, prefer "Yes"
        elif any(kw in field_lower for kw in ['experience', 'work', 'skill', 'qualified', 'eligible']):
            return "Yes"
        # For location/commute questions, prefer "Yes"
        elif any(kw in field_lower for kw in ['commut', 'locat', 'relocat', 'move', 'travel']):
            return "Yes"
        # For remote work questions, prefer "Yes"
        elif any(kw in field_lower for kw in ['remote', 'home working', 'work from home', 'telecommut']):
            logger.info(f"Auto-answering remote work question with 'Yes': {field_label}")
            return "Yes"
        # For visa/sponsorship questions, prefer "No"
        elif any(kw in field_lower for kw in ['visa', 'sponsor', 'right to work', 'work permit']):
            logger.info(f"Auto-answering visa/sponsorship question with 'No': {field_label}")
            return "No"
        # For education questions, prefer "Yes" (having the degree is better than not)
        elif any(kw in field_lower for kw in ['degree', 'education', 'bachelor', 'master']):
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
    """Get the answer for a field from the answers dictionary.
    
    ONLY use EXACT MATCHING to prevent auto-filling fields without explicit stored answers,
    with one exception: fields about years of experience are automatically filled with "2".
    
    This function will ONLY return an answer if:
    1. There is an EXACT match in the answers dictionary (exact case or case-insensitive)
    2. The field is about years of experience (starts with "How many years of work experience")
    
    Args:
        answers: Dictionary of stored answers
        field_label: The label text for the field
        
    Returns:
        str: The stored answer if found, None otherwise
    """
    # Special case: Auto-fill years of experience fields with "2"
    field_lower = field_label.lower()
    # Match various forms of years of experience questions
    if ('years of experience' in field_lower or 'years of work experience' in field_lower) and \
       ('how many' in field_lower or field_lower.startswith('years of')):
        logger.info(f"Auto-filling years of experience field: '{field_label}' with '2'")
        # Save this answer for future use
        answers[field_label] = "2"
        return "2"
    
    # Try exact match first
    if field_label in answers:
        return answers[field_label]
    
    # Try case-insensitive match (still exact, just ignoring case)
    for key, value in answers.items():
        if key.lower() == field_label.lower():
            return value
            
    # No matching answer found - DO NOT AUTO-FILL
    return None
