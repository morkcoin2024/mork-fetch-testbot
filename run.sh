#!/bin/bash

# Enhanced dual-service startup script for Mork F.E.T.C.H Bot
# Runs both web app (with scanners) and polling bot (scanner-free)

echo "🚀 Starting Mork F.E.T.C.H Bot Dual-Service Mode"
echo "================================================"

# Kill any existing instances
pkill -f "simple_polling_bot.py" 2>/dev/null || true
pkill -f "gunicorn" 2>/dev/null || true
sleep 2

# Function to start web app in background
start_web_app() {
    echo "🌐 Starting web application with scanners enabled..."
    export FETCH_ENABLE_SCANNERS=1
    nohup gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app > web_app.log 2>&1 &
    WEB_PID=$!
    echo "Web app started with PID: $WEB_PID"
    sleep 3
}

# Function to start polling bot in foreground
start_polling_bot() {
    echo "🤖 Starting Telegram polling bot..."
    export FETCH_ENABLE_SCANNERS=0
    python3 simple_polling_bot.py
}

# Auto-restart wrapper
restart_loop() {
    while true; do
        echo "$(date): Starting services..."

        # Start web app
        start_web_app

        # Start polling bot (foreground - main process)
        start_polling_bot

        echo "$(date): Polling bot stopped - restarting in 2 seconds..."
        sleep 2
    done
}

# Trap signals for clean shutdown
trap 'echo "Shutting down..."; pkill -f simple_polling_bot; pkill -f gunicorn; exit 0' SIGTERM SIGINT

# Start the restart loop
restart_loop
