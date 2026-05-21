import os

# Render dynamically assigns a port via the PORT environment variable.
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Increase timeout to allow the YOLO model to load into memory
timeout = 120

# Use a single worker for free tier to prevent running out of RAM (512MB limit)
workers = 1
