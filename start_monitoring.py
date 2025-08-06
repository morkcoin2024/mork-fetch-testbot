#!/usr/bin/env python3
"""
Start the monitoring service properly as a background process
"""
import subprocess
import sys
import os

def start_monitoring_service():
    """Start monitoring service in background"""
    try:
        # Start the monitoring service as a proper background process
        process = subprocess.Popen([
            sys.executable, 'monitoring_service.py'
        ], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        cwd='/home/runner/workspace'
        )
        
        print(f"Monitoring service started with PID: {process.pid}")
        return process.pid
        
    except Exception as e:
        print(f"Failed to start monitoring service: {e}")
        return None

if __name__ == "__main__":
    pid = start_monitoring_service()
    if pid:
        print("✅ Background monitoring service is now running!")
        print("It will continuously monitor for price changes and send notifications.")
    else:
        print("❌ Failed to start monitoring service")