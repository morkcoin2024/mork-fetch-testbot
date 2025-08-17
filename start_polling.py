#!/usr/bin/env python3
"""
Standalone polling bot starter that runs alongside the web app
"""
import os
import time
import subprocess
import sys

def start_polling_bot():
    """Start the polling bot in the background"""
    print("[START] Starting Telegram polling bot...")
    
    # Set environment
    env = os.environ.copy()
    env['FETCH_ENABLE_SCANNERS'] = '0'
    env['PYTHONUNBUFFERED'] = '1'
    
    # Clear webhook first
    token = env.get('TELEGRAM_BOT_TOKEN')
    if token:
        import requests
        try:
            requests.post(f'https://api.telegram.org/bot{token}/deleteWebhook', timeout=5)
            print("[START] Webhook cleared")
        except:
            pass
    
    # Remove lock file
    try:
        os.unlink('/tmp/mork_polling.lock')
    except:
        pass
    
    # Start polling bot
    cmd = [sys.executable, '-u', 'simple_polling_bot.py']
    
    while True:
        try:
            print("[START] Launching polling bot...")
            process = subprocess.Popen(
                cmd, 
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in process.stdout:
                print(f"[POLL] {line.rstrip()}")
                
        except KeyboardInterrupt:
            print("[START] Stopping...")
            if 'process' in locals():
                process.terminate()
            break
        except Exception as e:
            print(f"[START] Error: {e}")
            
        print("[START] Restarting in 3 seconds...")
        time.sleep(3)

if __name__ == "__main__":
    start_polling_bot()