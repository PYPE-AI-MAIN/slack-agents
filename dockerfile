# Use the official Python 3.11-slim image as a base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install required system dependencies (for certifi, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents (including .env file) into the container
COPY . /app

# Install pip and the necessary Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Set environment variables (optional: .env will be used for dynamic injection)
# If you want to hardcode or override env variables here, you can do so.
# Otherwise, use Docker Compose or docker run --env-file to inject .env at runtime.

# Expose port (optional, only needed if you're hosting a web server; not needed for socket mode)
EXPOSE 5000

# Load environment variables using python-dotenv (for local development or testing)
# This is used to automatically load environment variables from a .env file
RUN pip install python-dotenv

# Command to run the bot (it will start the Slack bot with Socket Mode)
CMD ["python", "bot.py"]
