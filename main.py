import logging
import ssl
import certifi
import os
from flask import Flask, request, redirect
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask for OAuth handling
app = Flask(__name__)

# Define the OAuth scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# OAuth callback URL
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
            SCOPES
        )

        # Get the credentials using the code from the URL
        credentials = flow.fetch_token(authorization_response=request.url)
        
        # Save the credentials (you can store them in a database, file, etc.)
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        # Save the token to a file (you can modify this to save it in a database)
        with open('user_tokens.json', 'w') as token_file:
            json.dump(token_data, token_file)

        logger.info("OAuth flow completed successfully and credentials saved.")
        
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

        # Start the bot (ensure your SlackService is correctly configured)
        logger.info("Starting Slack bot...")
        
        slack_service = SlackService()
        slack_service.start()
        logger.info("Slack bot is running!")

        # Start Flask server for OAuth callback handling (on port 8080)
        app.run(host='0.0.0.0', port=8080, ssl_context=ssl_context)  # Use SSL if required

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
