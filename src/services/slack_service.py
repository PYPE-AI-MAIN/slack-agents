from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta
import logging
import re
import pytz
from typing import Dict, Any, Optional, List
from .calendar_service import CalendarService, MeetingRequest
from openai import OpenAI
from dateutil import parser
from ..config import config
from ..utils.message_parser import parse_meeting_request, is_meeting_request

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self):
        """Initialize Slack service with bot token."""
        self.app = App(token=config.SLACK_BOT_TOKEN)
        self.calendar_service = CalendarService()
        self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        # Default timezone - can be made configurable per user
        self.default_timezone = pytz.timezone('America/New_York')  
        self.setup_handlers()

    def setup_handlers(self):
        """Set up all event handlers."""
        @self.app.event("app_mention")
        def handle_app_mention(body, say, logger):
            try:
                self._handle_app_mention(body, say)
            except Exception as e:
                logger.error(f"Error handling app mention: {e}")
                event = body.get("event", {})
                user_id = event.get("user")
                say(f"<@{user_id}> Sorry, I encountered an error processing your request.")

        @self.app.event("message")
        def handle_message(body, say, logger):
            try:
                self._handle_message(body, say)
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                event = body.get("event", {})
                user_id = event.get("user")
                say(f"<@{user_id}> Sorry, I encountered an error processing your message.")

        # Handle direct messages in channels
        @self.app.message("")
        def handle_direct_messages(message, say):
            try:
                if "subtype" not in message:
                    self._handle_direct_message(message, say)
            except Exception as e:
                logger.error(f"Error handling direct message: {e}")
                say("Sorry, I encountered an error processing your message.")

    def _handle_app_mention(self, body: Dict, say: callable):
        """Handle app mentions in channels."""
        event = body["event"]
        text = event["text"]
        user_id = event["user"]
        channel_id = event.get("channel")

        try:
            # Check if it's a meeting request
            if is_meeting_request(text):
                self._handle_meeting_request(text, user_id, say, channel_id)
            else:
                # Handle general conversation with OpenAI
                self._handle_chat_request(text, user_id, say)
        except Exception as e:
            logger.error(f"Error in handle_app_mention: {e}")
            say(f"<@{user_id}> Sorry, something went wrong while processing your request.")

    def _handle_message(self, body: Dict, say: callable):
        """Handle direct messages."""
        event = body["event"]
        if "subtype" not in event and event.get("channel_type") == "im":
            text = event["text"]
            user_id = event["user"]
            channel_id = event.get("channel")
            
            try:
                # Check if it's a meeting request
                if is_meeting_request(text):
                    self._handle_meeting_request(text, user_id, say, channel_id)
                else:
                    # Handle general conversation with OpenAI
                    self._handle_chat_request(text, user_id, say)
            except Exception as e:
                logger.error(f"Error in handle_message: {e}")
                say(f"<@{user_id}> Sorry, something went wrong while processing your message.")

    def _handle_direct_message(self, message: Dict, say: callable):
        """Handle direct messages in channels."""
        text = message.get("text", "")
        user_id = message.get("user")
        channel_id = message.get("channel")

        try:
            if is_meeting_request(text):
                self._handle_meeting_request(text, user_id, say, channel_id)
            else:
                self._handle_chat_request(text, user_id, say)
        except Exception as e:
            logger.error(f"Error in handle_direct_message: {e}")
            say(f"<@{user_id}> Sorry, something went wrong while processing your message.")

    def _handle_chat_request(self, text: str, user_id: str, say: callable):
        """Handle general chat requests using OpenAI."""
        try:
            # Remove any user mentions from the text
            clean_text = re.sub(r'<@[^>]+>', '', text).strip()
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",  # or your preferred model
                messages=[
                    {"role": "system", "content": "You are a helpful assistant in a Slack channel."},
                    {"role": "user", "content": clean_text}
                ]
            )
            
            bot_reply = response.choices[0].message.content
            say(f"<@{user_id}> {bot_reply}")
            
        except Exception as e:
            logger.error(f"Error in chat request: {e}")
            say(f"<@{user_id}> Sorry, I couldn't process your request at the moment.")

    def _handle_meeting_request(self, text: str, user_id: str, say: callable, channel_id: str = None):
        """Handle meeting scheduling requests."""
        try:
            # Check if user is authenticated
            if not self.calendar_service.is_user_authenticated(user_id):
                auth_url = self.calendar_service.get_auth_url(user_id)
                say(f"<@{user_id}> To schedule meetings, I need access to your Google Calendar. "
                    f"Please authenticate here: {auth_url}")
                return

            # Parse meeting details
            meeting_details = parse_meeting_request(text)
            if not meeting_details:
                say(f"<@{user_id}> I couldn't understand the meeting details. "
                    f"Please use format: schedule meeting with user@example.com at 2pm for 30 minutes")
                return

            # Convert time to user's timezone if not already set
            meeting_time = meeting_details['time']
            if meeting_time and not meeting_time.tzinfo:
                # First set the time to user's timezone
                local_time = self.default_timezone.localize(meeting_time)
                # Then convert to UTC for storage
                utc_time = local_time.astimezone(pytz.UTC)
                meeting_details['time'] = utc_time

            # Create meeting request
            meeting_request = MeetingRequest(
                title=meeting_details.get('title', 'Meeting'),
                attendees=meeting_details['attendees'],
                duration_minutes=meeting_details.get('duration', 30),
                start_time=meeting_details.get('time'),
                organizer_slack_id=user_id,
                description=f"Meeting scheduled via Slack by <@{user_id}>\nOriginal request: {meeting_details.get('original_text', '')}"
            )

            # Schedule the meeting
            result = self.calendar_service.schedule_meeting(meeting_request)

            if result['success']:
                # Convert UTC time back to user's timezone for display
                local_meeting_time = meeting_request.start_time.astimezone(self.default_timezone)
                meeting_time_str = local_meeting_time.strftime("%I:%M %p %Z on %B %d, %Y")
                
                # Calculate end time
                end_time = local_meeting_time + timedelta(minutes=meeting_request.duration_minutes)
                end_time_str = end_time.strftime("%I:%M %p")
                
                say(f"<@{user_id}> Meeting '{meeting_request.title}' scheduled!\n"
                    f"Time: {meeting_time_str} - {end_time_str}\n"
                    f"Attendees: {', '.join(meeting_request.attendees)}\n"
                    f"Duration: {meeting_request.duration_minutes} minutes\n"
                    f"Calendar link: {result['meeting_link']}\n"
                    f"Video call link: {result.get('video_link', 'No video link available')}")
            else:
                if result.get('auth_required'):
                    auth_url = self.calendar_service.get_auth_url(user_id)
                    say(f"<@{user_id}> Please authenticate first: {auth_url}")
                else:
                    say(f"<@{user_id}> Sorry, I couldn't schedule the meeting: {result['error']}")

        except Exception as e:
            logger.error(f"Error handling meeting request: {e}")
            say(f"<@{user_id}> Sorry, something went wrong while scheduling the meeting. Error: {str(e)}")

    def start(self):
        """Start the Slack bot."""
        try:
            logger.info("Starting Slack bot in socket mode...")
            handler = SocketModeHandler(self.app, config.SLACK_APP_TOKEN)
            handler.start()
        except Exception as e:
            logger.error(f"Failed to start Slack bot: {e}")
            raise