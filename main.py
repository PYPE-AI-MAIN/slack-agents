import logging
import ssl
import certifi
import os
import json
from flask import Flask, request, redirect, session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from cryptography.fernet import Fernet
from src.services.slack_service import SlackService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask for OAuth handling
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Environment variables
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
PORT = int(os.getenv('PORT', 8080))
GOOGLE_CREDENTIALS = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
PROD_REDIRECT_URI = os.getenv('PROD_REDIRECT_URI')

# OAuth configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Initialize encryption for tokens
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def get_redirect_uri():
    """Get the appropriate redirect URI based on environment."""
    if ENVIRONMENT == 'production':
        return PROD_REDIRECT_URI
    return 'https://localhost:8080/oauth2callback'

def create_flow(redirect_uri=None):
    """Create OAuth flow from environment credentials."""
    if redirect_uri is None:
        redirect_uri = get_redirect_uri()
    
    # Create a flow instance from client config
    flow = Flow.from_client_config(
        client_config=GOOGLE_CREDENTIALS,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

def encrypt_token(token_data):
    """Encrypt token data before storing."""
    return cipher_suite.encrypt(json.dumps(token_data).encode())

def decrypt_token(encrypted_token):
    """Decrypt stored token data."""
    return json.loads(cipher_suite.decrypt(encrypted_token).decode())

@app.before_request
def before_request():
    """Ensure all requests are secure."""
    if not request.is_secure and ENVIRONMENT != 'development':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.route('/authorize')
def authorize():
    """Initiate the OAuth flow."""
    try:
        flow = create_flow()
        
        # Generate and store state parameter
        state = os.urandom(16).hex()
        session['oauth_state'] = state
        
        # Generate authorization URL
        authorization_url, _ = flow.authorization_url(
            state=state,
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        logger.info("OAuth flow initiated successfully")
        return redirect(authorization_url)
        
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}")
        return "Failed to initiate authorization", 500

@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth callback."""
    error = request.args.get('error')
    if error:
        logger.error(f"OAuth error: {error}")
        return f"Authorization failed: {error}", 400

    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        logger.error("Missing authorization code")
        return "Error: Missing authorization code", 400
        
    if not state or state != session.get('oauth_state'):
        logger.error("Invalid state parameter")
        return "Invalid state parameter", 400

    try:
        # Create flow with the current URL as redirect URI
        flow = create_flow(redirect_uri=request.base_url)
        
        # Get the credentials using the code
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Prepare token data
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        # Encrypt token data
        encrypted_token = encrypt_token(token_data)
        
        # Create tokens directory if it doesn't exist
        os.makedirs('user_tokens', exist_ok=True)
        
        # Set secure permissions
        os.chmod('user_tokens', 0o700)
        
        # Save the encrypted token
        token_path = f'user_tokens/{credentials.client_id}_token.json'
        with open(token_path, 'wb') as token_file:
            token_file.write(encrypted_token)
        
        os.chmod(token_path, 0o600)

        logger.info("OAuth flow completed successfully and credentials saved")
        
        # Clear the session state
        session.pop('oauth_state', None)
        
        return "Authorization successful! You can close this window."
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return f"Error: Authorization failed", 500

def setup_ssl():
    """Setup SSL configuration."""
    if ENVIRONMENT == 'production':
        return None  # Let the production server handle SSL
    else:
        # Use certifi for development
        os.environ['SSL_CERT_FILE'] = certifi.where()
        return ssl.create_default_context(cafile=certifi.where())

def main():
    """Main entry point for the application."""
    try:
        # Setup SSL for development
        ssl_context = setup_ssl()
        logger.info("SSL configuration completed")

        # Start the Slack bot
        logger.info("Starting Slack bot...")
        slack_service = SlackService()
        slack_service.start()
        logger.info("Slack bot is running!")

        # Configure server settings
        server_settings = {
            'host': '0.0.0.0',  # Listen on all interfaces
            'port': PORT,
            'threaded': True
        }
        
        # Add SSL context in development
        if ENVIRONMENT == 'development':
            server_settings['ssl_context'] = ssl_context
        
        if ENVIRONMENT == 'production':
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
            
            @app.after_request
            def add_security_headers(response):
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'DENY'
                response.headers['X-XSS-Protection'] = '1; mode=block'
                return response

        # Start Flask server
        app.run(**server_settings)

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

if __name__ == "__main__":
    main()