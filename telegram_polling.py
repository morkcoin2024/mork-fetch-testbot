#!/usr/bin/env python3
"""
Minimal Telegram polling bot for Mork F.E.T.C.H Bot
Runs independently of Flask to avoid import conflicts
"""
import os
import time
import logging
import requests
import json
from filelock import FileLock

# Setup logging  
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('mork_poll')

# Configuration
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
API_BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'
LOCK_PATH = '/tmp/mork_polling.lock'

def process_command(text, chat_id, user_id):
    """Process Telegram commands and return response"""
    if not text:
        return None
    
    text = text.strip()
    cmd = text.lower()
    
    if cmd == '/ping':
        return '🏓 Pong! Mork F.E.T.C.H Bot is alive and ready to fetch profits!'
    
    elif cmd == '/help':
        return ('🐕 *Mork F.E.T.C.H Bot* - The Degens\' Best Friend!\n\n'
                '*Commands:*\n'
                '/ping - Test connection\n'
                '/help - Show commands\n'
                '/wallet - Wallet info\n'
                '/autosell_status - AutoSell status\n'
                '/scanner_status - Scanner status\n'
                '/status - System overview')
    
    elif cmd == '/wallet':
        return ('👛 *Wallet Status*\n\n'
                'Status: Not configured\n'
                'Use `/wallet_new` to create a new wallet')
    
    elif cmd == '/autosell_status':
        return ('🚀 *AutoSell Status*\n\n'
                'Status: OFF\n'
                'Active Rules: 0\n'
                'Use `/autosell_on` to enable')
    
    elif cmd == '/scanner_status':
        return ('🔍 *Scanner Status*\n\n'
                'Solscan: Active\n'
                'Birdeye: Enabled\n'
                'DexScreener: Ready\n'
                'Total discoveries: 20+ tokens')
    
    elif cmd == '/status':
        return ('⚡ *Mork F.E.T.C.H Bot Status*\n\n'
                '🟢 Telegram: Connected\n'
                '🟢 Scanners: Active\n'
                '🔴 Wallet: Not configured\n'
                '🔴 AutoSell: OFF\n'
                '🟢 System: Operational')
    
    elif cmd.startswith('/'):
        clean_cmd = cmd.replace('\n', ' ')[:50]
        return f'Command not recognized: {clean_cmd}\n\nUse /help for available commands.'
    
    return None

def send_message(chat_id, text):
    """Send message to Telegram chat"""
    try:
        response = requests.post(f'{API_BASE}/sendMessage', 
                               json={
                                   'chat_id': chat_id, 
                                   'text': text,
                                   'parse_mode': 'Markdown'
                               }, 
                               timeout=10)
        return response.status_code == 200
    except Exception as e:
        log.error(f'Send error: {e}')
        return False

def run_polling():
    """Main polling loop"""
    log.info('🤖 Mork F.E.T.C.H Bot polling started')
    offset = 0
    
    while True:
        try:
            # Get updates
            response = requests.get(f'{API_BASE}/getUpdates', 
                                  params={'offset': offset, 'timeout': 10}, 
                                  timeout=15)
            
            if response.status_code != 200:
                log.warning(f'API error: {response.status_code}')
                time.sleep(5)
                continue
            
            data = response.json()
            if not data.get('ok'):
                log.error(f'API not ok: {data.get("description", "Unknown error")}')
                time.sleep(5)
                continue
            
            updates = data.get('result', [])
            if updates:
                log.info(f'Processing {len(updates)} updates')
                
                for update in updates:
                    update_id = update['update_id']
                    offset = update_id + 1
                    
                    msg = update.get('message', {})
                    if not msg:
                        continue
                    
                    text = msg.get('text', '')
                    chat_id = msg.get('chat', {}).get('id')
                    user_id = msg.get('from', {}).get('id')
                    username = msg.get('from', {}).get('username', 'unknown')
                    
                    if text and chat_id:
                        log.info(f'Command: "{text}" from @{username} ({user_id})')
                        
                        response_text = process_command(text, chat_id, user_id)
                        if response_text:
                            success = send_message(chat_id, response_text)
                            log.info(f'Response sent: {success}')
            
            time.sleep(1)
            
        except Exception as e:
            log.error(f'Polling error: {e}')
            time.sleep(5)

def main():
    """Main entry point with file lock"""
    if not BOT_TOKEN:
        log.error('TELEGRAM_BOT_TOKEN not set')
        return
    
    try:
        with FileLock(LOCK_PATH, timeout=1):
            log.info(f'Lock acquired: {LOCK_PATH}')
            run_polling()
    except Exception as e:
        log.error(f'Lock error: {e}')

if __name__ == '__main__':
    main()