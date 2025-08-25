#!/usr/bin/env python3
"""
Production runner for Replit Deploy - runs both web app and polling bot
"""
import logging
import os
import signal
import subprocess
import sys
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProductionRunner:
    def __init__(self):
        self.web_process = None
        self.poll_process = None
        self.running = True

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

        if self.web_process:
            self.web_process.terminate()
        if self.poll_process:
            self.poll_process.terminate()

        sys.exit(0)

    def start_web_app(self):
        """Start the Flask web application with scanners enabled"""
        logger.info("[WEB] Starting Flask application with scanners...")

        env = os.environ.copy()
        env["FETCH_ENABLE_SCANNERS"] = "1"  # Enable scanners for web app

        cmd = ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"]

        self.web_process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        logger.info(f"[WEB] Started with PID {self.web_process.pid}")

        # Monitor web process output
        def monitor_web():
            if self.web_process and self.web_process.stdout:
                for line in self.web_process.stdout:
                    logger.info(f"[WEB] {line.rstrip()}")

        threading.Thread(target=monitor_web, daemon=True).start()

    def start_polling_bot(self):
        """Start the Telegram polling bot"""
        logger.info("[POLL] Starting Telegram polling bot...")

        env = os.environ.copy()
        env["FETCH_ENABLE_SCANNERS"] = "0"  # Disable scanners for polling bot

        cmd = [sys.executable, "-u", "polling_worker.py"]

        self.poll_process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        logger.info(f"[POLL] Started with PID {self.poll_process.pid}")

        # Monitor polling process output
        def monitor_poll():
            if self.poll_process and self.poll_process.stdout:
                for line in self.poll_process.stdout:
                    logger.info(f"[POLL] {line.rstrip()}")

        threading.Thread(target=monitor_poll, daemon=True).start()

    def monitor_processes(self):
        """Monitor both processes and restart if needed"""
        while self.running:
            try:
                # Check web process
                if self.web_process and self.web_process.poll() is not None:
                    logger.warning("[WEB] Process died, restarting...")
                    self.start_web_app()

                # Check polling process
                if self.poll_process and self.poll_process.poll() is not None:
                    logger.warning("[POLL] Process died, restarting...")
                    self.start_polling_bot()

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5)

    def run(self):
        """Run both services"""
        logger.info("🚀 Starting Mork F.E.T.C.H Bot production runner...")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        try:
            # Start both services
            self.start_web_app()
            time.sleep(2)  # Give web app time to start
            self.start_polling_bot()

            logger.info("✅ Both services started successfully")
            logger.info("📊 Web app: http://0.0.0.0:5000 (scanners enabled)")
            logger.info("🤖 Telegram bot: polling mode (scanners disabled)")

            # Monitor processes
            self.monitor_processes()

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            if self.web_process:
                self.web_process.terminate()
            if self.poll_process:
                self.poll_process.terminate()


def main():
    """Main entry point"""
    runner = ProductionRunner()
    runner.run()


if __name__ == "__main__":
    main()
