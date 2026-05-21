import os
import subprocess
import time

print("Starting ngrok tunnel...")
print("This will create an HTTPS link for mobile testing")
print()

try:
    from pyngrok import ngrok
    
    # Set your authtoken if you have one (optional)
    # ngrok.set_auth_token("YOUR_TOKEN")
    
    # Create tunnel
    url = ngrok.connect(5000, "http")
    print("=" * 60)
    print("🌐 HTTPS LINK FOR MOBILE:")
    print("=" * 60)
    print(url)
    print("=" * 60)
    print()
    print("Use this link in your mobile browser!")
    print("Press Ctrl+C to stop the tunnel")
    print()
    
    # Keep running
    while True:
        time.sleep(1)
        
except ImportError:
    print("pyngrok not installed!")
    print("Run: pip install pyngrok")
except Exception as e:
    print(f"Error: {e}")
    print()
    print("Alternative: Use localtunnel")
    print("Run: npm install -g localtunnel")
    print("Then: lt --port 5000")

input("\nPress Enter to exit...")
