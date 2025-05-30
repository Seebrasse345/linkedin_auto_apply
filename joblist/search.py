from urllib.parse import urlencode, quote_plus
import logging

logger = logging.getLogger(__name__)

# --- Mappings based on URL analysis ---
DISTANCE_KM_MAP = {
    8: 5,
    15: 10,
    40: 25,
    80: 50,
}

DATE_POSTED_MAP = {
    "Past 24 hours": "r86400",
    "Past Week": "r604800",
    "Past Month": "r2592000", # Assuming 30 days
    "Any Time": None # Parameter omitted for any_time
}

REMOTE_MAP = {
    "on_site": "1",
    "remote": "2",
    "hybrid": "3"
}

EXPERIENCE_MAP = {
    "internship": "1",
    "entry_level": "2",
    "associate": "3",
    "mid_senior_level": "4",
    "director": "5",
    "executive": "6"
}

JOB_TYPE_MAP = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "volunteer": "V",
    "internship": "I"
}
# --- End Mappings ---


def _build_filter_param(config_key: str,
                        mapping: dict,
                        filters: dict,
                        allow_multiple: bool = False) -> str | None:
    """Helper to build comma-separated filter parameters."""
    values = filters.get(config_key, [])
    if not isinstance(values, list):
         values = [values] # Ensure it's a list

    mapped_values = [mapping[val] for val in values if val in mapping]

    if not mapped_values:
        return None

    if allow_multiple:
        return ",".join(sorted(mapped_values)) # Sort for consistent URL
    elif len(mapped_values) == 1:
         return mapped_values[0]
    else:
         logger.warning(f"Multiple values provided for single-value filter '{config_key}'. Using first valid value: {mapped_values[0]}")
         return mapped_values[0]

#profile name str or None if not given
def construct_search_url(profile: dict, profile_name: str | None = None) -> str:
    """
    Constructs a LinkedIn job search URL from a configuration profile.

    Args:
        profile: A dictionary representing a search profile from config.yml.
        profile_name: Name of the profile being processed

    Returns:
        A string containing the fully constructed LinkedIn job search URL.
    """
    # Check for direct collection URL options first (these bypass normal search)
    if 'filters' in profile:
        filters = profile['filters']
        
        # Auto Easy Apply Collection
        if filters.get('auto_easy', False):
            logger.info(f"Using LinkedIn's Easy Apply collection for profile '{profile_name}'")
            return "https://www.linkedin.com/jobs/collections/easy-apply/?discover=recommended&discoveryOrigin=JOBS_HOME_JYMBII"
        
        # Auto Recommended Collection
        if filters.get('auto_recommend', False):
            logger.info(f"Using LinkedIn's Recommended jobs collection for profile '{profile_name}'")
            return "https://www.linkedin.com/jobs/collections/recommended/?discover=recommended&discoveryOrigin=JOBS_HOME_JYMBII"
    else:
        filters = {}
    
    # Continue with regular URL construction if direct collections not requested
    base_url = "https://www.linkedin.com/jobs/search/"

    # Check for location and geoId, which are still required
    required_keys = ['location', 'geoId']
    if not all(key in profile for key in required_keys):
        missing = [key for key in required_keys if key not in profile]
        logger.warning(f"Search profile '{profile_name}' is missing required keys: {missing}")
        return None
        
    # Query is optional now - it can be empty (the key still needs to exist though)
    if 'query' not in profile:
        logger.warning(f"Search profile '{profile_name}' is missing 'query' key. Using empty query.")
        profile['query'] = ''

    params = {}

    # --- Core Search Terms ---
    # Only add the keywords parameter if query is not empty
    if profile['query'].strip():
        params['keywords'] = profile['query']
    params['location'] = profile['location'] # Location string might be sufficient
    params['geoId'] = profile['geoId'] # Use configured Geo ID

    # --- Easy Apply Filter ---
    params['f_AL'] = 'true' # Always apply Easy Apply filter

    # --- Low Number of Applicants Filter ---
    low_number_applicants = filters.get('low_number_applicants', False)
    if low_number_applicants:
        params['f_EA'] = 'true'
        logger.info("Including f_EA=true filter for jobs with fewer applicants")

    # --- Distance Filter ---
    distance_km = filters.get('distance_km')
    if distance_km and distance_km in DISTANCE_KM_MAP:
        params['distance'] = str(DISTANCE_KM_MAP[distance_km])
    elif distance_km:
         logger.warning(f"Unsupported distance_km value: {distance_km}. Omitting distance filter.")

    # --- Date Posted Filter ---
    date_posted_filter = filters.get('date_posted')
    if date_posted_filter:
        if date_posted_filter == "custom_hours":
            custom_hours = filters.get('date_posted_custom_hours_value')
            if isinstance(custom_hours, int) and 1 <= custom_hours <= 23:
                seconds = custom_hours * 3600
                params['f_TPR'] = f"r{seconds}"
                logger.info(f"Applying custom date posted filter: {custom_hours} hours ({seconds} seconds)")
            else:
                logger.warning(f"Invalid 'date_posted_custom_hours_value': {custom_hours}. Omitting date filter.")
        elif date_posted_filter != "Any Time": # Existing logic for predefined non-custom, non-anytime values
            time_param = DATE_POSTED_MAP.get(date_posted_filter)
            if time_param:
                params['f_TPR'] = time_param
            else:
                logger.warning(f"Unsupported date_posted value: {date_posted_filter}. Omitting date filter.")
        # If 'Any Time', f_TPR is correctly omitted by this logic

    # --- Remote Filter (f_WT) ---
    remote_param = _build_filter_param('remote', REMOTE_MAP, filters, allow_multiple=True)
    if remote_param:
        params['f_WT'] = remote_param

    # --- Experience Level Filter (f_E) ---
    exp_param = _build_filter_param('experience', EXPERIENCE_MAP, filters, allow_multiple=True)
    if exp_param:
         params['f_E'] = exp_param

    # --- Job Type Filter (f_JT) ---
    job_type_param = _build_filter_param('job_type', JOB_TYPE_MAP, filters, allow_multiple=True)
    if job_type_param:
        params['f_JT'] = job_type_param
        logger.info(f"Added job type filter: f_JT={job_type_param}")

    # --- Other potential filters (add as needed based on config/plan) ---
    # Example: Company (f_C) - needs company IDs?

    # --- Static Parameters ---
    params['origin'] = 'JOB_SEARCH_PAGE_JOB_FILTER'
    params['refresh'] = 'true' # Keep refresh=true as seen in examples


    # --- Encode and Construct URL ---
    # Use quote_plus for space encoding (%2B) if needed, but urlencode handles standard cases
    encoded_params = urlencode(params, quote_via=quote_plus)

    full_url = f"{base_url}?{encoded_params}"
    logger.info(f"Constructed search URL: {full_url}")
    return full_url 