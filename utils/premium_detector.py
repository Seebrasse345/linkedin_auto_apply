import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

def check_and_handle_premium_redirect(page: Page) -> bool:
    """
    Checks if the current page URL contains LinkedIn premium path and navigates back if detected.
    Handles various URL formats including linkedin.com/premium/* patterns.
    
    Args:
        page: The Playwright Page object
        
    Returns:
        bool: True if premium page was detected and back navigation was attempted, False otherwise
    """
    try:
        current_url = page.url
        
        # Check if URL contains LinkedIn premium pattern (more flexible matching)
        if is_premium_page(current_url):
            logger.warning(f"Detected LinkedIn premium page redirect: {current_url}")
            logger.info("Attempting to navigate back to avoid premium subscription flow")
            
            try:
                # Navigate back to previous page
                page.go_back(wait_until='domcontentloaded', timeout=10000)
                logger.info("Successfully navigated back from premium page")
                
                # Wait a moment for the page to stabilize
                page.wait_for_timeout(2000)
                
                # Log the new URL after going back
                new_url = page.url
                logger.info(f"Current URL after going back: {new_url}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to navigate back from premium page: {e}")
                # If back navigation fails, try alternative approaches
                try:
                    # Try to find and click a back button
                    back_button = page.locator('button[aria-label="Back"], button[aria-label="Go back"], a[aria-label="Back"]')
                    if back_button.count() > 0:
                        logger.info("Found back button on premium page, clicking it")
                        back_button.first.click(timeout=5000)
                        page.wait_for_timeout(2000)
                        logger.info(f"Clicked back button, current URL: {page.url}")
                        return True
                except Exception as back_btn_error:
                    logger.error(f"Failed to click back button on premium page: {back_btn_error}")
                
                return True  # Still return True since we detected the premium page
                
        return False
        
    except Exception as e:
        logger.error(f"Error in check_and_handle_premium_redirect: {e}")
        return False


def is_premium_page(url: str) -> bool:
    """
    Robust utility to check if a URL is a LinkedIn premium page.
    Handles various URL formats and patterns.
    
    Args:
        url: The URL to check
        
    Returns:
        bool: True if URL contains LinkedIn premium path, False otherwise
    """
    if not url:
        return False
    
    # Convert to lowercase for case-insensitive matching
    url_lower = url.lower()
    
    # Check for various LinkedIn premium URL patterns
    premium_patterns = [
        "linkedin.com/premium",  # Matches any subdomain or protocol
        "linkedin.com/premium/",  # With trailing slash
    ]
    
    # Check if any premium pattern is found in the URL
    for pattern in premium_patterns:
        if pattern in url_lower:
            return True
    
    return False 