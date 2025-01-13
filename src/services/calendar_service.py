from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
from ..auth.google_auth import GoogleAuthManager

logger = logging.getLogger(__name__)

@dataclass
class MeetingRequest:
    """Data class for meeting requests."""
    title: str
    attendees: List[str]
    duration_minutes: int = 60
    start_time: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    organizer_slack_id: str = None

class CalendarService:
    def __init__(self):
        """Initialize calendar service."""
        self.auth_manager = GoogleAuthManager()
    
    def is_user_authenticated(self, slack_user_id: str) -> bool:
        """Check if user is authenticated."""
        return self.auth_manager.is_user_authenticated(slack_user_id)
    
    def get_auth_url(self, slack_user_id: str) -> str:
        """Get authentication URL for a user."""
        return self.auth_manager.get_auth_url(slack_user_id)
    
    def schedule_meeting(self, request: MeetingRequest) -> Dict[str, Any]:
        """Schedule a meeting using user's Google Calendar."""
        try:
            # Get user credentials
            credentials = self.auth_manager.get_user_credentials(request.organizer_slack_id)
            if not credentials:
                return {
                    'success': False,
                    'error': 'Not authenticated',
                    'auth_required': True
                }
            
            # Build service for this user
            service = build('calendar', 'v3', credentials=credentials)
            
            # Set default start time if not provided
            if not request.start_time:
                request.start_time = datetime.now(pytz.UTC) + timedelta(hours=1)
                request.start_time = request.start_time.replace(
                    minute=0, second=0, microsecond=0
                )
            
            end_time = request.start_time + timedelta(minutes=request.duration_minutes)
            
            event = {
                'summary': request.title,
                'description': request.description or '',
                'start': {
                    'dateTime': request.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [{'email': attendee} for attendee in request.attendees],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 15},
                    ],
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"meeting_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            }
            
            if request.location:
                event['location'] = request.location
            
            # Insert the event
            event = service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            return {
                'success': True,
                'meeting_link': event.get('htmlLink'),
                'video_link': event.get('conferenceData', {})
                    .get('entryPoints', [{}])[0]
                    .get('uri', 'No video link available'),
                'meeting_id': event.get('id')
            }
            
        except HttpError as e:
            logger.error(f"Calendar API error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in schedule_meeting: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def get_upcoming_meetings(
        self,
        slack_user_id: str,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Get upcoming meetings for a specific user."""
        try:
            credentials = self.auth_manager.get_user_credentials(slack_user_id)
            if not credentials:
                return {
                    'success': False,
                    'error': 'Not authenticated',
                    'auth_required': True
                }
            
            service = build('calendar', 'v3', credentials=credentials)
            
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            formatted_events = []
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                formatted_events.append({
                    'summary': event.get('summary', 'No title'),
                    'start_time': start,
                    'link': event.get('htmlLink'),
                    'attendees': [
                        attendee['email'] 
                        for attendee in event.get('attendees', [])
                    ] if event.get('attendees') else []
                })
            
            return {'success': True, 'events': formatted_events}
            
        except Exception as e:
            logger.error(f"Error fetching upcoming meetings: {e}")
            return {'success': False, 'error': str(e)}