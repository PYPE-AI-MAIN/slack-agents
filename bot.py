from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI
import os
from dotenv import load_dotenv
import ssl
import certifi

# Set the default SSL context to use certifi's certificates
os.environ['SSL_CERT_FILE'] = certifi.where()
ssl_context = ssl.create_default_context(cafile=certifi.where())
# Load environment variables from .env file
load_dotenv()

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")  # Socket Mode App Token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initiate open ai
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Slack App
app = App(token=SLACK_BOT_TOKEN)

# Listener for 'app_mention' event
@app.event("app_mention")
def handle_app_mention_events(body, say, logger):
    logger.info(body)
    user_query = body["event"]["text"]
    user = body["event"]["user"]
    
    # Call OpenAI API
    try:
        # Use a valid OpenAI model like gpt-3.5-turbo
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use a correct model here
            messages=[{"role": "user", "content": user_query}]
        )
        bot_reply = response.choices[0].message.content

        # Respond in the channel
        say(f"<@{user}> {bot_reply}")
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        say(f"Sorry <@{user}>, something went wrong while processing your query.")


# Listener for direct messages
@app.event("message")
def handle_message_events(body, say, logger):
    logger.info(body)
    event = body.get("event", {})
    user = event.get("user")
    channel = event.get("channel")
    message_text = event.get("text")

    # Ensure it's a DM (channel name starts with 'D')
    if "subtype" not in event and channel.startswith("D"):
        try:
            # Use a valid OpenAI model like gpt-3.5-turbo
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Correct model here
                messages=[{"role": "user", "content": message_text}]
            )
            bot_reply = response.choices[0].message.content

            # Send the response back as a DM
            say(channel=channel, text=bot_reply)
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            say(channel=channel, text="Sorry, I encountered an error.")

# Example: Respond to any message
# @app.message("")
# def respond_to_message(message, say):
#     user_query = message.get("text", "")
#     user = message.get("user", "")

#     if user_query:
#         # Call OpenAI API for response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": user_query}]
#         )
        
#         bot_reply = response.choices[0].message.content

#         # Send reply
#         say(f"<@{user}> {bot_reply}")

# Start Socket Mode
if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
