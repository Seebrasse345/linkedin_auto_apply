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
OPENAI_TEMPERATURE = 0.8

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

def answer_generator(question: str, field_type: str = None, job_data: Dict[str, Any] = None) -> str:
    """Generate an answer for an Easy Apply question based on past answers, CV, and job data.
    
    Args:
        question: The question to answer, may include options for select/radio fields
        field_type: The type of field (text, select, radio, etc.)
        job_data: Optional job data including description, only used for text fields
        
    Returns:
        str: The answer, either a number for select/radio fields or text for text fields
    """
    # Load past answers
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    answers_path = os.path.join(project_root, 'answers', 'default.json')
    try:
        with open(answers_path, 'r', encoding='utf-8') as f:
            past_answers = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load past answers: {e}")
        past_answers = {}
    # Read CV content
    cv_content = read_cv()
    # System prompt for GPT
    system_message = (
        "You are an expert assistant for selecting the correct numeric option for LinkedIn Easy Apply questions.\n"
        "You are given the user's past answers to similar linkedin questions in JSON format and the user's CV You must use this information to select the best option.\n"
        "When asked a question, select the option number that best matches the user's history and past answers to these questions and profile.\n"
        "If no past data, choose the most willing option e.g willing to learn/commute etc available unless its a blatant lie. Do not fabricate options not present.\n"
        "Always output only the single number corresponding to your selection, with no additional text. YOU MUST ALWAYS select an answer\n"
        "IF THE QUESTION IS A TEXT FIELD QUESTION THAT IS NOT A SELECT QUESTION AND IS OF THE LIKES of Why inspired you to apply etc DO NOT SELECT a number option instead write a proffesional answer using the CV and job description in full THIS IS THE ONLY CASE YOU SHOULD RETURN A TEXT ANSWER IF NUMERICAL MULTIPLE CHOISE options e.g 1. 2. 3. or 1.Yes 2.NO etc are AVAILABLE NEVER WRITE TEXT.\n"
        "DO NOT REPEAT THE AVAILABLE OPTIONS IN YOUR OUTPUT. Some extra information for the more critical options NO driving license, Has British passports is a british citizen , IS WILLING TO GET A SECURITY CLEARANCE HOWEVER DOES NOT POSSESS ONE HAS POSSESSED ONE AND NO ACTIVE ONE BUT WILLING TO always willing to commute, ALWAYS COMFORTABLE WITH WORKING ANYWHERE etc \n"
        " IF IT IS A SIMPLE QUESTION ANSWER IN A SIMPLE WAY NO NEED TO MAKE IT COMPLICATED FOR example do you have a  non-compete should just be a no or under 5-10 words\n"
        " If the question is like Headline just give a cover letter headline BE CONSICE ON SIMPLE QUESTIONS\n"
        "Extra information user is Male, age 23, has BSc physics, living in Sheffield, England, United Kingdom, for years of experience quesitons use heuristics and CV information if not default to 2. For more generic questions like why do you want the role answer appropriately proffessionally using the CV and job description in full \n"
        f"Here are the user's past answers in JSON format: {json.dumps(past_answers)}\n\n"
        f"Here is the USER'S CV:\n{cv_content}\n\n"
    )
    # User prompt content
    user_prompt = "Here is the question and the available options for you to answer\n"
    user_prompt += f"Question: {question}"
    
    # Add job description for text fields
    if field_type in ["text", "textarea"] and job_data and "description" in job_data:
        user_prompt += f"\n\nThis question is about a {job_data.get('title', 'job')} at {job_data.get('company', 'a company')}\n"
        user_prompt += f"Job Description:\n{job_data.get('description', '')}\n"
        user_prompt += "\nPlease provide a professional response related to this job description."
    # Prepare API request
    api_key = get_openai_api_key()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    messages = [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_prompt}
    ]
    data = {
        'model': OPENAI_MODEL,
        'messages': messages
    }
    # Add retry mechanism for rate limit errors (429)
    max_retries = 3
    retry_delay = 60  # Initial delay in seconds
    
    for retry in range(max_retries + 1):
        try:
            response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=30)
            
            # Check specifically for rate limit errors (429)
            if response.status_code == 429:
                if retry < max_retries:
                    wait_time = retry_delay * (2 ** retry)  # Exponential backoff
                    logger.warning(f"Rate limit (429) reached. Waiting {wait_time} seconds before retry {retry+1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Max retries reached for rate limit. Question: '{question}'")
                    # Return a special tuple to indicate this is a fallback answer that shouldn't be saved
                    return (False, "")
            
            # For other HTTP errors
            response.raise_for_status()
            
            raw_content = response.json()['choices'][0]['message']['content'].strip()
            
            # For text fields, return the entire response without extraction
            if field_type in ["text", "textarea"]:
                logger.info(f"Generated text answer for question '{question}': '{raw_content[:50]}...'")
                return raw_content
            
            # For non-text fields, extract only the numeric selection
            match = re.search(r'\d+', raw_content)
            if match:
                selection = match.group(0)
                logger.info(f"Generated numeric answer for question '{question}': {selection}")
                return selection
            else:
                logger.warning(f"No numeric answer found in API response for question '{question}': '{raw_content}'")
                # If no numeric answer found but we have text, return it for text fields
                if field_type in ["text", "textarea"] and raw_content:
                    return raw_content
                return (False, False)  # Special format indicating fallback shouldn't be saved
                
        except requests.exceptions.HTTPError as e:
            if retry < max_retries and '429' in str(e):
                wait_time = retry_delay * (2 ** retry)
                logger.warning(f"Rate limit (429) reached. Waiting {wait_time} seconds before retry {retry+1}/{max_retries}")
                time.sleep(wait_time)
            else:
                logger.error(f"HTTP error generating answer for question '{question}': {e}")
                return (False, "")  # Special format indicating fallback shouldn't be saved
                
        except Exception as e:
            logger.error(f"Failed to generate answer for question '{question}': {e}")
            return (False, "")  # Special format indicating fallback shouldn't be saved
