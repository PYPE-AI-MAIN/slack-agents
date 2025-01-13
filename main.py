import logging
import ssl
import certifi
import os
from src.services.slack_service import SlackService
from src.config import config
from flask import Flask, request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask for OAuth handling
app = Flask(__name__)

# Google OAuth callback URL
@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth callback."""
    code = request.args.get('code')
    if not code:
        return "Error: Missing authorization code", 400

    try:
        # Initialize the OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json',  # Path to your credentials
            ['https://www.googleapis.com/auth/calendar']
        )

        # Get the credentials using the code from the URL
        credentials = flow.fetch_token(authorization_response=request.url)
        
        # Save or use the credentials here
        # This is where you'd save the credentials to a file, database, etc.
        logger.info(f"OAuth flow completed successfully for code: {code}")
        
        return "Authorization successful!"
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return f"Error: {e}", 500

def setup_ssl():
    """Setup SSL configuration."""
    os.environ['SSL_CERT_FILE'] = certifi.where()
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return ssl_context

def main():
    """Main entry point for the Slack bot."""
    try:
        # Setup SSL
        ssl_context = setup_ssl()
        logger.info("SSL configuration completed")

        # Start the bot
        logger.info("Starting Slack bot...")
        
        slack_service = SlackService()
        slack_service.start()
        logger.info("Slack bot is running!")

        # Start Flask server for OAuth callback handling
        app.run(host='0.0.0.0', port=8080, ssl_context=ssl_context)  # Use SSL if required

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
