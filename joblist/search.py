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
    "past_24h": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000", # Assuming 30 days
    "any_time": None # Parameter omitted for any_time
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


def construct_search_url(profile: dict) -> str:
    """
    Constructs a LinkedIn job search URL from a configuration profile.

    Args:
        profile: A dictionary representing a search profile from config.yml.

    Returns:
        A string containing the fully constructed LinkedIn job search URL.

    Raises:
        ValueError: If required profile keys are missing.
    """
    base_url = "https://www.linkedin.com/jobs/search/"

    required_keys = ['query', 'location', 'geoId', 'filters']
    if not all(key in profile for key in required_keys):
        missing = [key for key in required_keys if key not in profile]
        raise ValueError(f"Search profile is missing required keys: {missing}")

    filters = profile['filters']
    params = {}

    # --- Core Search Terms ---
    params['keywords'] = profile['query']
    params['location'] = profile['location'] # Location string might be sufficient
    params['geoId'] = profile['geoId'] # Use configured Geo ID

    # --- Easy Apply Filter ---
    params['f_AL'] = 'true' # Always apply Easy Apply filter

    # --- Distance Filter ---
    distance_km = filters.get('distance_km')
    if distance_km and distance_km in DISTANCE_KM_MAP:
        params['distance'] = str(DISTANCE_KM_MAP[distance_km])
    elif distance_km:
         logger.warning(f"Unsupported distance_km value: {distance_km}. Omitting distance filter.")

    # --- Date Posted Filter ---
    date_posted_filter = filters.get('date_posted')
    if date_posted_filter and date_posted_filter != "any_time":
         time_param = DATE_POSTED_MAP.get(date_posted_filter)
         if time_param:
             params['f_TPR'] = time_param
         else:
             logger.warning(f"Unsupported date_posted value: {date_posted_filter}. Omitting date filter.")

    # --- Remote Filter (f_WT) ---
    remote_param = _build_filter_param('remote', REMOTE_MAP, filters, allow_multiple=True)
    if remote_param:
        params['f_WT'] = remote_param

    # --- Experience Level Filter (f_E) ---
    exp_param = _build_filter_param('experience', EXPERIENCE_MAP, filters, allow_multiple=True)
    if exp_param:
         params['f_E'] = exp_param

    # --- Other potential filters (add as needed based on config/plan) ---
    # Example: Job Type (f_JT) - map "full-time", "part-time" etc.
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