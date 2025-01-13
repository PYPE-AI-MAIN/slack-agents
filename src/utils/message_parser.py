import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dateutil import parser
from dateutil.relativedelta import relativedelta, TU, MO, WE, TH, FR, SA, SU
import logging
import pytz

logger = logging.getLogger(__name__)

def is_meeting_request(text: str) -> bool:
    """
    Determine if the message is a meeting request.
    
    Args:
        text: The message text to analyze
        
    Returns:
        bool: True if the message appears to be a meeting request
    """
    meeting_keywords = [
        r'schedule\s+(?:a\s+)?meeting',
        r'set\s+up\s+(?:a\s+)?meeting',
        r'book\s+(?:a\s+)?meeting',
        r'organize\s+(?:a\s+)?meeting',
        r'plan\s+(?:a\s+)?meeting',
        r'calendar\s+invite',
        r'schedule\s+(?:a\s+)?call',
        r'set\s+up\s+(?:a\s+)?call',
        r'can you book',
        r'please book',
    ]
    
    text = text.lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in meeting_keywords)

def parse_future_date(text: str) -> Optional[datetime]:
    """
    Parse future date references from text.
    """
    text = text.lower()
    now = datetime.now()
    
    # Handle "next Tuesday", "next Wednesday" etc.
    day_mapping = {
        'monday': MO, 'tuesday': TU, 'wednesday': WE, 
        'thursday': TH, 'friday': FR, 'saturday': SA, 'sunday': SU
    }
    
    for day, day_const in day_mapping.items():
        if f'next {day}' in text:
            # Get next occurrence of that day
            next_day = now + relativedelta(weekday=day_const(+1))
            return next_day
    
    # Handle "tomorrow"
    if 'tomorrow' in text:
        return now + timedelta(days=1)
    
    # Handle "today"
    if 'today' in text:
        return now
    
    return None

def parse_time_str(time_str: str, base_date: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse time string and combine with base date.
    """
    try:
        # If no base date provided, use today
        if not base_date:
            base_date = datetime.now()
        
        # Parse the time
        time = parser.parse(time_str)
        
        # Combine base date with parsed time
        return datetime.combine(
            base_date.date(),
            time.time()
        )
    except Exception as e:
        logger.error(f"Error parsing time string: {e}")
        return None

def parse_meeting_request(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse meeting details from text message.
    """
    try:
        # Extract email addresses
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        emails = re.findall(email_pattern, text)

        if not emails:
            return None

        # First, try to find the date (next Tuesday, tomorrow, etc.)
        base_date = parse_future_date(text)
        
        # Extract time
        time_pattern = r'(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm))'
        time_match = re.search(time_pattern, text, re.IGNORECASE)
        
        meeting_time = None
        if time_match:
            time_str = time_match.group(1)
            if base_date:
                meeting_time = parse_time_str(time_str, base_date)
            else:
                # If no specific date found, use tomorrow if the parsed time is earlier than now
                parsed_time = parse_time_str(time_str)
                if parsed_time:
                    if parsed_time.time() < datetime.now().time():
                        # If the time is earlier than now, assume tomorrow
                        meeting_time = parse_time_str(time_str, datetime.now() + timedelta(days=1))
                    else:
                        meeting_time = parse_time_str(time_str, datetime.now())

        # Extract duration
        duration_pattern = r'for (\d+)\s*(?:min(?:ute)?s?|hours?)?'
        duration_match = re.search(duration_pattern, text)
        
        # Extract title/subject
        title_patterns = [
            r'(?:subject|title|about|regarding)\s+["\'](.+?)["\']',
            r'["\'](.+?)["\']'
        ]
        
        title_match = None
        for pattern in title_patterns:
            match = re.search(pattern, text)
            if match:
                title_match = match
                break

        return {
            'attendees': emails,
            'time': meeting_time or (datetime.now() + timedelta(hours=1)),
            'duration': int(duration_match.group(1)) if duration_match else 30,
            'title': title_match.group(1) if title_match else 'Meeting',
            'original_text': text  # Keep original text for reference
        }

    except Exception as e:
        logger.error(f"Error parsing meeting request: {e}")
        return None

def clean_message(text: str) -> str:
    """Clean up message text by removing mentions and formatting."""
    # Remove user mentions
    text = re.sub(r'<@\w+>', '', text)
    # Remove channel mentions
    text = re.sub(r'<#\w+>', '', text)
    # Remove URL formatting
    text = re.sub(r'<(https?://[^|>]+)[^>]*>', r'\1', text)
    return text.strip()