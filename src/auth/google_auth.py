from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json
from typing import Optional, Dict
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class GoogleAuthManager:
    def __init__(self):
        """Initialize Google Auth Manager."""
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.tokens_dir = Path('user_tokens')
        self.tokens_dir.mkdir(exist_ok=True)
        self.credentials_path = 'credentials.json'

    def get_auth_url(self, slack_user_id: str) -> str:
        """Generate OAuth URL for user authorization."""
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path,
                self.SCOPES
            )
            
            # Initialize the local server flow
            flow.run_local_server(port=0)
            
            # Get credentials from the flow
            credentials = flow.credentials
            
            # Save the credentials
            if credentials:
                self._save_user_credentials(slack_user_id, credentials)
                return "Authentication successful! You can now schedule meetings."
            
            return flow.authorization_url()[0]
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}")
            raise

    def get_user_credentials(self, slack_user_id: str) -> Optional[Credentials]:
        """Get user's Google credentials."""
        try:
            token_path = self.tokens_dir / f"{slack_user_id}_token.json"
            
            if not token_path.exists():
                logger.info(f"No token found for user {slack_user_id}")
                return None
            
            with open(token_path, 'r') as f:
                token_data = json.load(f)
            
            credentials = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            
            # Refresh if expired
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_user_credentials(slack_user_id, credentials)
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return None

    def is_user_authenticated(self, slack_user_id: str) -> bool:
        """Check if user is authenticated."""
        try:
            credentials = self.get_user_credentials(slack_user_id)
            return bool(credentials and not credentials.expired)
        except Exception as e:
            logger.error(f"Error checking authentication: {e}")
            return False

    def _save_user_credentials(self, slack_user_id: str, credentials: Credentials):
        """Save user credentials to file."""
        try:
            token_path = self.tokens_dir / f"{slack_user_id}_token.json"
            token_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            with open(token_path, 'w') as f:
                json.dump(token_data, f)
                
            logger.info(f"Saved credentials for user {slack_user_id}")
            
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            raise