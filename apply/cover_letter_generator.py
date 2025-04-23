"""
Cover letter generator for LinkedIn job applications.
Uses OpenAI API to generate customized cover letters based on job descriptions and CV.
"""
import os
import logging
import json
import time
import re
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# OpenAI API Configuration
# Store API key in an environment variable or config file for better security in production
def get_openai_api_key() -> str:
    """Get the OpenAI API key from environment or config.
    
    In the future, this could be enhanced to retrieve from a secure environment variable or config file.
    
    Returns:
        str: OpenAI API key
    """
    # Hardcoded for now - this is a placeholder and should be replaced with proper security later
    # In a production environment, this would be a major security issue
    # Using the old key provided
    api_key = "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"
    
    # Log the first and last few characters for debugging, NEVER log the full key
    if api_key:
        safe_key_preview = f"{api_key[:5]}...{api_key[-5:]}"
        logger.info(f"Using OpenAI API key: {safe_key_preview}")
    else:
        logger.error("No OpenAI API key available")
        
    return api_key

OPENAI_MODEL = "gpt-4.1-2025-04-14"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MAX_TOKENS = 1000
OPENAI_TEMPERATURE = 0.7

def read_cv() -> str:
    """
    Read the CV content from the cv.txt file.
    
    Returns:
        str: The CV content as text
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cv_path = os.path.join(base_dir, 'cv.txt')
        
        with open(cv_path, 'r', encoding='utf-8') as file:
            cv_content = file.read()
        
        logger.info(f"Successfully loaded CV from {cv_path}")
        return cv_content
    except Exception as e:
        logger.error(f"Failed to read CV file: {e}")
        return ""

def generate_cover_letter(job_data: Dict[str, Any], answers: Dict[str, Any]) -> str:
    """
    Generate a customized cover letter based on the job description using OpenAI API.
    
    Args:
        job_data: Dictionary containing job details (title, company, description)
        answers: Dictionary of stored user answers/preferences
        
    Returns:
        str: Generated cover letter text
    """
    logger.info(f"Generating cover letter with OpenAI API for {job_data.get('title', 'Unknown Position')} at {job_data.get('company', 'Unknown Company')}")
    
    # Get profile information from answers
    first_name = answers.get('First name', 'Matthaios')
    last_name = answers.get('Last name', 'Markatis')
    full_name = f"{first_name} {last_name}"
    
    # Extract key information from job data
    job_title = job_data.get('title', 'the position')
    company_name = job_data.get('company', 'the company')
    description = job_data.get('description', '')
    location = job_data.get('location', '')
    
    # Read CV content
    cv_content = read_cv()
    
    # Create the prompt for OpenAI
    prompt = f"""
You are an expert cover letter writer. Your task is to write a professional, personalized cover letter for a job application.

JOB DETAILS:
- Position: {job_title}
- Company: {company_name}
- Location: {location}
- Job Description: {description}

APPLICANT CV:
{cv_content}

REQUIREMENTS:
1. Write a professional cover letter from the perspective of {full_name}
2. Address it to the Hiring Manager
3. Reference key skills and experiences from the CV that directly relate to the job requirements
4. Keep it concise (300-400 words maximum)
5. Show enthusiasm for the specific role and company
6. Highlight 2-3 specific achievements or projects from the CV that align with the job
7. Use a professional, confident tone
8. Include a proper salutation and closing
9. DO NOT include the date or address blocks
10. Format it as plain text for a form field
11. DO NOT LEAVE ANY PLACE HOLDERS OR BLANK FIELDS

Cover letter:
"""
    
    try:
        # Get API key securely
        api_key = get_openai_api_key()
        if not api_key:
            logger.error("No OpenAI API key available")
            print("\n[APPLICATION FORM] Error: No OpenAI API key available. Using fallback cover letter.")
            return generate_fallback_cover_letter(job_data, answers)
            
        # Configure API request
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "gpt-4o-2024-05-13",  # Use newer model that definitely exists
            "messages": [
                {"role": "system", "content": "You are a professional cover letter writer. Write concise, well-structured cover letters."},
                {"role": "user", "content": prompt}
            ]
            # Removed timeout as it's not a valid OpenAI parameter
        }
        
        # Make the API call with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling OpenAI API to generate cover letter (attempt {attempt+1})")
                print(f"\n[APPLICATION FORM] Generating custom cover letter using AI... (attempt {attempt+1})")
                
                # Add more robust error handling with timeout
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                # If we get an error response, log it in detail before raising
                if response.status_code != 200:
                    error_detail = response.text[:200] if response.text else "No error details"
                    logger.error(f"OpenAI API error (status {response.status_code}): {error_detail}")
                    
                response.raise_for_status()  # Raises HTTPError for 4XX/5XX status codes
                
                # Parse response
                response_data = response.json()
                
                if 'choices' not in response_data or len(response_data['choices']) == 0:
                    logger.error(f"Unexpected API response format: {response_data}")
                    print("\n[APPLICATION FORM] Error: Unexpected API response. Using fallback cover letter.")
                    return generate_fallback_cover_letter(job_data, answers)
                    
                cover_letter = response_data['choices'][0]['message']['content'].strip()
                
                # Verify the cover letter looks valid - less strict validation
                if len(cover_letter) < 50:
                    logger.warning(f"Generated cover letter may be too short: {cover_letter}")
                    print("\n[APPLICATION FORM] Warning: Generated cover letter is too short. Retrying...")
                    # Try again if the response seems invalid
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                        
                # Even if it's not perfect, use it if we've retried multiple times
                if attempt >= 2 and len(cover_letter) >= 100:
                    logger.info("Using current cover letter after multiple retries")
                    break
                
                # Log success
                logger.info(f"Successfully generated cover letter for {job_title} at {company_name} using OpenAI API")
                print("\n[APPLICATION FORM] Successfully generated AI cover letter!")
                return cover_letter
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"API call failed, retrying in {wait_time} seconds: {e}")
                    time.sleep(wait_time)
                else:
                    raise
        
    except Exception as e:
        logger.error(f"Failed to generate cover letter with OpenAI API: {e}")
        # Fall back to a template cover letter
        return generate_fallback_cover_letter(job_data, answers)

def generate_fallback_cover_letter(job_data: Dict[str, Any], answers: Dict[str, Any]) -> str:
    """
    Generate a fallback cover letter if the API call fails.
    
    Args:
        job_data: Dictionary containing job details
        answers: Dictionary of stored user answers/preferences
        
    Returns:
        str: Fallback cover letter text
    """
    # Get profile information from answers
    first_name = answers.get('First name', 'Matthaios')
    last_name = answers.get('Last name', 'Markatis')
    
    # Extract key information from job data
    job_title = job_data.get('title', 'the position')
    company_name = job_data.get('company', 'your company')
    
    # Create a simple fallback cover letter
    cover_letter = f"""Dear Hiring Manager,

I am writing to express my interest in the {job_title} position at {company_name}. I was excited to learn about this opportunity and believe my skills and experience align well with the requirements of the role.

As a Data Scientist and ML Engineer with experience in full-stack development, I bring a diverse skillset that encompasses Python programming, machine learning model development, and building end-to-end AI applications. My background in physics has provided me with strong analytical and problem-solving skills that I apply to technical challenges.

Some of my key projects include developing a wildfire detection system with machine learning, creating a personal AI image generation mobile application, and building an autonomous drone navigation system. These experiences have equipped me with the technical knowledge and practical skills necessary for this role.

I am particularly interested in joining {company_name} because of its reputation for innovation. I am confident that my background and enthusiasm make me a strong candidate for this position.

I welcome the opportunity to discuss how my qualifications match your needs. Thank you for considering my application.

Sincerely,
{first_name} {last_name}
"""
    
    return cover_letter
