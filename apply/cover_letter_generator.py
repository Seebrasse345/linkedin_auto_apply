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
def get_openai_api_key():
    """Get the OpenAI API key from environment or config."""
    # NOTE: In a production environment, this should be stored in environment variables or a secure vault
    # This is a temporary solution for the current implementation
    return "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"

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
            
        # Call OpenAI API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": OPENAI_MAX_TOKENS,
            "temperature": OPENAI_TEMPERATURE
        }
        
        # Make the API call with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling OpenAI API to generate cover letter (attempt {attempt+1})")
                print(f"\n[APPLICATION FORM] Generating custom cover letter using AI... (attempt {attempt+1})")
                
                response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=60)
                
                # Check for API errors
                if response.status_code == 401:
                    logger.error("OpenAI API key is invalid or expired")
                    print("\n[APPLICATION FORM] Error: OpenAI API key is invalid or expired. Using fallback cover letter.")
                    return generate_fallback_cover_letter(job_data, answers)
                    
                response.raise_for_status()
                
                # Parse response
                response_data = response.json()
                
                if 'choices' not in response_data or len(response_data['choices']) == 0:
                    logger.error(f"Unexpected API response format: {response_data}")
                    print("\n[APPLICATION FORM] Error: Unexpected API response. Using fallback cover letter.")
                    return generate_fallback_cover_letter(job_data, answers)
                    
                cover_letter = response_data['choices'][0]['message']['content'].strip()
                
                # Verify the cover letter looks valid
                if len(cover_letter) < 100 or 'Dear' not in cover_letter or 'Sincerely' not in cover_letter:
                    logger.warning(f"Generated cover letter may be incomplete: {cover_letter[:50]}...")
                    print("\n[APPLICATION FORM] Warning: Generated cover letter may be incomplete. Retrying...")
                    # Try again if the response seems invalid
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                
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
