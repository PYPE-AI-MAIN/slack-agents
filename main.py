import logging
from src.services.slack_service import SlackService
from src.config import config
import ssl
import certifi
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()