from dotenv import load_dotenv
import os
import logging
from pathlib import Path
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        load_dotenv()
        
        # Required environment variables
        self.SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
        self.SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')
        
        # Google Calendar credentials
        # Get the JSON content from the environment variable
        credentials_content = os.getenv("GOOGLE_CREDENTIALS_JSON")

        # Load the JSON string into a Python dictionary
        credentials_dict = json.loads(credentials_content)

        # Write the formatted JSON back into the file
        with open("credentials.json", "w") as f:
            json.dump(credentials_dict, f, indent=4)

        self.GOOGLE_CREDENTIALS_FILE = './credentials.json'
        # Create necessary directories
        self.USER_TOKENS_DIR = Path('user_tokens')
        self.USER_TOKENS_DIR.mkdir(exist_ok=True)
        
        # Open AI credentials
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

        self._validate_config()
    
    def _validate_config(self):
        """Validate all required configurations are present."""
        if not self.SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
        if not self.SLACK_APP_TOKEN:
            raise ValueError("SLACK_APP_TOKEN not found in environment variables")
        if not Path(self.GOOGLE_CREDENTIALS_FILE).exists():
            raise ValueError(f"Google credentials file not found: {self.GOOGLE_CREDENTIALS_FILE}")

# Create global config instance
config = Config()