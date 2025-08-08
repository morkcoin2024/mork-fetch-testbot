#!/usr/bin/env python3
"""
Emergency Stop System for Mork F.E.T.C.H Bot
Provides immediate trading halt capabilities to prevent losses
"""

import asyncio
import logging
import time
import os
from typing import Dict, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class EmergencyStopSystem:
    """Global emergency stop system for all trading operations"""
    
    def __init__(self):
        self.stopped_users: Set[str] = set()
        self.global_stop = False
        self.stop_file = "EMERGENCY_STOP.flag"
        self.user_stops_file = "user_stops.txt"
        
    def activate_global_stop(self, reason: str = "Emergency stop activated") -> Dict:
        """Activate global emergency stop for all users"""
        self.global_stop = True
        
        # Create stop flag file
        with open(self.stop_file, 'w') as f:
            f.write(f"GLOBAL_EMERGENCY_STOP\n")
            f.write(f"Activated: {datetime.now()}\n")
            f.write(f"Reason: {reason}\n")
        
        logger.critical(f"🚨 GLOBAL EMERGENCY STOP ACTIVATED: {reason}")
        
        return {
            "success": True,
            "type": "global_stop",
            "message": f"All trading stopped globally: {reason}",
            "timestamp": datetime.now().isoformat()
        }
    
    def activate_user_stop(self, chat_id: str, reason: str = "User emergency stop") -> Dict:
        """Activate emergency stop for specific user"""
        self.stopped_users.add(str(chat_id))
        
        # Save to file for persistence
        with open(self.user_stops_file, 'a') as f:
            f.write(f"{chat_id}:{datetime.now().isoformat()}:{reason}\n")
        
        logger.warning(f"🛑 USER EMERGENCY STOP: {chat_id} - {reason}")
        
        return {
            "success": True,
            "type": "user_stop",
            "user": chat_id,
            "message": f"Trading stopped for user: {reason}",
            "timestamp": datetime.now().isoformat()
        }
    
    def is_stopped(self, chat_id: str = None) -> bool:
        """Check if trading is stopped globally or for specific user"""
        # Check global stop flag file
        if os.path.exists(self.stop_file):
            self.global_stop = True
            
        if self.global_stop:
            return True
            
        if chat_id and str(chat_id) in self.stopped_users:
            return True
            
        return False
    
    def get_stop_status(self, chat_id: str = None) -> Dict:
        """Get current emergency stop status"""
        if self.is_stopped(chat_id):
            if self.global_stop:
                return {
                    "stopped": True,
                    "type": "global",
                    "message": "Global emergency stop is active"
                }
            elif chat_id and str(chat_id) in self.stopped_users:
                return {
                    "stopped": True,
                    "type": "user",
                    "message": f"Emergency stop active for user {chat_id}"
                }
        
        return {
            "stopped": False,
            "message": "No emergency stops active"
        }
    
    def deactivate_global_stop(self) -> Dict:
        """Deactivate global emergency stop"""
        self.global_stop = False
        
        if os.path.exists(self.stop_file):
            os.remove(self.stop_file)
        
        logger.info("✅ Global emergency stop deactivated")
        
        return {
            "success": True,
            "message": "Global emergency stop deactivated",
            "timestamp": datetime.now().isoformat()
        }
    
    def deactivate_user_stop(self, chat_id: str) -> Dict:
        """Deactivate emergency stop for specific user"""
        self.stopped_users.discard(str(chat_id))
        
        logger.info(f"✅ User emergency stop deactivated for {chat_id}")
        
        return {
            "success": True,
            "message": f"Emergency stop deactivated for user {chat_id}",
            "timestamp": datetime.now().isoformat()
        }

# Global emergency stop instance
emergency_stop = EmergencyStopSystem()

def check_emergency_stop(chat_id: str = None) -> bool:
    """Quick check if emergency stop is active"""
    return emergency_stop.is_stopped(chat_id)

def activate_emergency_stop(chat_id: str = None, reason: str = "Manual emergency stop") -> Dict:
    """Activate emergency stop (global or user-specific)"""
    if chat_id:
        return emergency_stop.activate_user_stop(chat_id, reason)
    else:
        return emergency_stop.activate_global_stop(reason)