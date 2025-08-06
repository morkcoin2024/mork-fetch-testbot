#!/usr/bin/env python3
"""
Persistent monitoring service that runs as a proper daemon
"""
import time
import subprocess
import sys
import os

def run_monitoring_daemon():
    """Run monitoring service in a persistent loop"""
    while True:
        try:
            print("Starting monitoring service...")
            
            # Run the monitoring service
            result = subprocess.run([
                sys.executable, 'monitoring_service.py'
            ], 
            cwd='/home/runner/workspace',
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
            )
            
            print(f"Monitoring service output: {result.stdout}")
            if result.stderr:
                print(f"Monitoring service errors: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("Monitoring service timed out, restarting...")
        except Exception as e:
            print(f"Monitoring service error: {e}")
        
        print("Restarting monitoring service in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    run_monitoring_daemon()